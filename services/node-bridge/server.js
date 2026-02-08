import express from "express";
import SteamUser from "steam-user";
import SteamTotp from "steam-totp";

const {
  STEAM_BRIDGE_INTERNAL_TOKEN,
  PRESENCE_DEBUG_TOKEN,
} = process.env;

const app = express();

// CORS for browser clients (dashboard is on a different Railway origin)
app.use((req, res, next) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type,Authorization,X-Bridge-Token");
  if (req.method === "OPTIONS") return res.sendStatus(204);
  next();
});
app.use(express.json());

const MATCH_GRACE_MS = 5 * 60 * 1000;
const BOT_PATTERN = /\bbot\b|\bbots\b|bot[_\s-]?match/;

const sessions = new Map(); // bridgeId -> session
const defaultBridgeByUser = new Map(); // userId -> bridgeId

function normalizeKey(key) {
  return String(key || "").toLowerCase();
}

function getAuthToken(req) {
  const header = req.headers["authorization"] || "";
  if (header.toLowerCase().startsWith("bearer ")) {
    return header.slice(7).trim();
  }
  return req.headers["x-bridge-token"] || "";
}

app.use((req, res, next) => {
  if (req.path === "/health") return next();
  const token = (STEAM_BRIDGE_INTERNAL_TOKEN || "").trim();
  if (!token) return res.status(500).json({ error: "bridge_token_missing" });
  const provided = String(getAuthToken(req) || "").trim();
  if (!provided || provided !== token) {
    return res.status(403).json({ error: "forbidden" });
  }
  next();
});

function getRichPresenceValue(rp, rpRaw, key) {
  const target = normalizeKey(key);

  if (rp && typeof rp === "object") {
    for (const [k, v] of Object.entries(rp)) {
      if (normalizeKey(k) === target) return v;
    }
  }

  if (Array.isArray(rpRaw)) {
    const entry = rpRaw.find((e) => normalizeKey(e.key) === target);
    if (entry) return entry.value;
  }

  return undefined;
}

/**
 * Demo Hero detection (reliable based on your debug dump):
 *   param0 = "#demo_hero_mode_name"
 *
 * We also allow any param0 containing "demo" as a safe fallback.
 */
function isDotaDemo(rp, rpRaw) {
  const p0 = getRichPresenceValue(rp, rpRaw, "param0");
  if (!p0) return false;
  const v = String(p0).toLowerCase();
  return v.includes("demo_hero_mode_name") || v.includes("demo");
}

function isBotMatch(rp, rpRaw) {
  const status = String(rp?.status || "").toLowerCase();
  const display = String(rp?.steam_display || "").toLowerCase();
  const lobby = String(rp?.lobby || "").toLowerCase();
  const param0 = String(getRichPresenceValue(rp, rpRaw, "param0") || "").toLowerCase();
  const param1 = String(getRichPresenceValue(rp, rpRaw, "param1") || "").toLowerCase();
  return [status, display, lobby, param0, param1].some((value) => BOT_PATTERN.test(value));
}

function isInDotaMatch(rp) {
  if (!rp || typeof rp !== "object") return false;

  const status = String(rp.status || "").toLowerCase();
  const display = String(rp.steam_display || "").toLowerCase();
  const lobby = String(rp.lobby || "").toLowerCase();

  const hasLevel = rp.level !== undefined;
  const hasMatchId = rp.matchid !== undefined || rp.watchable_match_id !== undefined;
  const hasStateOrMode = rp.state !== undefined || rp.mode !== undefined;
  const hasLobbyId = rp.lobby_id !== undefined || rp.lobbyid !== undefined || lobby.length > 0;

  const lobbyStates = ["run", "serversetup"];
  const indicators = [
    "heroselection",
    "strategytime",
    "playing",
    "ranked",
    "turbo",
    "captains",
    "draft",
    "match",
    "private_lobby",
    "finding_match",
  ];

  const lobbyStateHit = lobbyStates.some((kw) => lobby.includes(`lobby_state: ${kw}`));

  return (
    hasLevel ||
    hasMatchId ||
    hasLobbyId ||
    hasStateOrMode ||
    lobbyStateHit ||
    indicators.some((kw) => display.includes(kw) || status.includes(kw))
  );
}

function isInDotaMatchRaw(raw) {
  if (!Array.isArray(raw)) return false;
  const lobbyEntry = raw.find((e) => (e.key || "").toLowerCase() === "lobby");
  if (lobbyEntry && typeof lobbyEntry.value === "string") {
    const lv = lobbyEntry.value.toLowerCase();
    if (lv.includes("lobby_state: run") || lv.includes("lobby_state: serversetup")) return true;
  }
  return false;
}

function extractGameMode(rp, rpRaw, lobbyRaw) {
  const direct =
    getRichPresenceValue(rp, rpRaw, "game_mode") ??
    getRichPresenceValue(rp, rpRaw, "gamemode") ??
    getRichPresenceValue(rp, rpRaw, "mode");
  if (direct !== null && direct !== undefined) {
    const value = String(direct).trim();
    if (value) return value;
  }

  const lobbyText = String(lobbyRaw || "");
  const match = lobbyText.match(/game_mode:\s*([^\s]+)/i);
  return match ? match[1] : "";
}

function toHeroDisplay(token) {
  if (!token) return "";
  const normalized = token.startsWith("#") ? token.slice(1) : token;
  if (!normalized.startsWith("npc_dota_hero_")) return normalized;
  const name = normalized.replace("npc_dota_hero_", "").replace(/_/g, " ");
  return name.replace(/\b\w/g, (c) => c.toUpperCase());
}

function parseIntMaybe(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === "number" && Number.isFinite(value)) return Math.floor(value);
  const raw = String(value).trim();
  if (!raw) return null;
  const parsed = Number.parseInt(raw, 10);
  return Number.isNaN(parsed) ? null : parsed;
}

function extractHeroToken(rp, rpRaw) {
  const candidates = [rp?.param2, rp?.hero, rp?.hero_name, rp?.heroname, rp?.npc_dota_hero];
  for (const value of candidates) {
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  if (Array.isArray(rpRaw)) {
    const entry = rpRaw.find((e) => (e.key || "").toLowerCase() === "param2");
    if (entry && typeof entry.value === "string" && entry.value.trim()) {
      return entry.value.trim();
    }
  }
  return "";
}

function extractMatchSeconds(rp, rpRaw) {
  const nowSec = Math.floor(Date.now() / 1000);
  const keys = [
    "matchtime",
    "match_time",
    "game_time",
    "gametime",
    "elapsed",
    "elapsed_time",
    "match_duration",
    "duration",
    "time",
    "start_time",
    "starttime",
  ];

  for (const key of keys) {
    const raw = getRichPresenceValue(rp, rpRaw, key);
    const value = parseIntMaybe(raw);
    if (value === null) continue;

    if (key.includes("start")) {
      let start = value;
      if (start > 1e12) start = Math.floor(start / 1000);
      const elapsed = nowSec - start;
      if (elapsed > 0 && elapsed < 12 * 60 * 60) return elapsed;
      continue;
    }

    let seconds = value;
    if (seconds > 1e12) seconds = Math.floor(seconds / 1000);
    if (seconds > 12 * 60 * 60 && seconds < nowSec) {
      const elapsed = nowSec - seconds;
      if (elapsed > 0 && elapsed < 12 * 60 * 60) return elapsed;
    }
    if (seconds >= 0 && seconds < 12 * 60 * 60) return seconds;
  }

  return null;
}

function formatMatchTime(seconds) {
  if (seconds === null || seconds === undefined) return null;
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

function extractMatchId(rp, rpRaw) {
  const keys = [
    "watchablegameid",
    "watchable_game_id",
    "watchable_match_id",
    "watchablematchid",
    "matchid",
    "match_id",
  ];
  for (const key of keys) {
    const raw = getRichPresenceValue(rp, rpRaw, key);
    if (raw === null || raw === undefined) continue;
    const value = String(raw).trim();
    if (value) return value;
  }
  return null;
}

function updateMatchStart(matchStart, id64, inMatch, matchId, heroKey) {
  const now = Date.now();
  const entry = matchStart.get(id64);

  if (inMatch) {
    if (!entry) {
      matchStart.set(id64, {
        startedAt: now,
        matchId: matchId || null,
        heroKey: heroKey || null,
        lastSeenAt: now,
        graceUntil: null,
      });
      return { entry: matchStart.get(id64), reset: true };
    }

    const heroChanged = heroKey && entry.heroKey && heroKey !== entry.heroKey;
    const matchChanged = matchId && entry.matchId && matchId !== entry.matchId;
    const reset = heroChanged || matchChanged;

    if (reset) {
      entry.startedAt = now;
      entry.matchId = matchId || null;
      entry.heroKey = heroKey || null;
    } else {
      if (matchId && !entry.matchId) entry.matchId = matchId;
      if (heroKey && !entry.heroKey) entry.heroKey = heroKey;
    }

    entry.lastSeenAt = now;
    entry.graceUntil = null;
    return { entry, reset };
  }

  if (!entry) return;
  if (!entry.graceUntil) entry.graceUntil = now + MATCH_GRACE_MS;
  if (entry.graceUntil <= now) matchStart.delete(id64);
  return { entry, reset: false };
}

function derivePresence(data, matchStart) {
  const rp = data.rich_presence || {};
  const rpRaw = data.rich_presence_raw || [];

  const lobbyRaw =
    rp.lobby ||
    (Array.isArray(rpRaw)
      ? rpRaw.find((e) => (e.key || "").toLowerCase() === "lobby")?.value || ""
      : "");

  const lobbyLower = String(lobbyRaw || "").toLowerCase();
  const lobbyStateHit = /lobby_state:\s*(run|serversetup)/.test(lobbyLower);

  const gameModeRaw = extractGameMode(rp, rpRaw, lobbyRaw);
  const gameModeLower = String(gameModeRaw || "").toLowerCase();
  const isCustomGame = gameModeLower.includes("custom");
  const gameModeLabel = isCustomGame ? "Custom Game" : null;

  const statusLower = String(rp.status || "").toLowerCase();
  const displayLower = String(rp.steam_display || "").toLowerCase();
  const statusKeywords = ["private_lobby", "finding_match", "playing", "match", "ranked", "turbo"];
  const statusHit = statusKeywords.some(
    (kw) => statusLower.includes(kw) || displayLower.includes(kw)
  );

  const matchId = extractMatchId(rp, rpRaw);

  const demo = isDotaDemo(rp, rpRaw);

  const inBotMatch = !demo && isBotMatch(rp, rpRaw);

  const inMatch =
    !demo &&
    !isCustomGame &&
    (inBotMatch || isInDotaMatch(rp) || isInDotaMatchRaw(rpRaw) || lobbyStateHit || statusHit);

  const inGame = !!(
    data.in_game ||
    data.appid ||
    lobbyRaw ||
    statusHit ||
    demo ||
    inBotMatch ||
    isCustomGame
  );

  const heroToken = extractHeroToken(rp, rpRaw);
  const heroKey = normalizeKey(heroToken);

  const update = updateMatchStart(matchStart, data.steamid64, inMatch, matchId, heroKey || null);

  const heroName = toHeroDisplay(heroToken);
  const heroLevel = null;

  let matchSeconds = extractMatchSeconds(rp, rpRaw);
  if (update?.reset) {
    matchSeconds = 0;
  }

  if (!update?.reset && matchSeconds !== null && matchSeconds > 0) {
    const expectedStart = Date.now() - matchSeconds * 1000;
    const entry = matchStart.get(data.steamid64);
    if (!entry || Math.abs(entry.startedAt - expectedStart) > 5000) {
      matchStart.set(data.steamid64, {
        startedAt: expectedStart,
        matchId: matchId || entry?.matchId || null,
        heroKey: heroKey || entry?.heroKey || null,
        lastSeenAt: Date.now(),
        graceUntil: null,
      });
    }
  }

  if ((matchSeconds === null || matchSeconds <= 0) && inMatch) {
    const entry = matchStart.get(data.steamid64);
    if (entry?.startedAt) {
      matchSeconds = Math.max(0, Math.floor((Date.now() - entry.startedAt) / 1000));
    }
  }

  const matchTime = formatMatchTime(matchSeconds);

  return {
    rp,
    rpRaw,
    lobbyRaw,
    inMatch,
    inGame,
    demo,
    inBotMatch,
    inCustomGame: isCustomGame,
    gameModeRaw,
    gameModeLabel,
    matchId,
    heroToken,
    heroName,
    heroLevel,
    matchSeconds,
    matchTime,
  };
}

function requireDebugToken(req, res, next) {
  if (PRESENCE_DEBUG_TOKEN) {
    const token = req.query.token || req.headers["x-debug-token"];
    if (token !== PRESENCE_DEBUG_TOKEN) {
      return res.status(403).json({ error: "forbidden" });
    }
  }
  next();
}

function buildDebugView(data, matchStart) {
  const derived = derivePresence(data, matchStart);

  const rawPairs = Array.isArray(derived.rpRaw)
    ? derived.rpRaw.map((e) => ({ key: e.key, value: e.value }))
    : Object.entries(derived.rpRaw || {}).map(([key, value]) => ({ key, value }));

  const rpPairs =
    derived.rp && typeof derived.rp === "object"
      ? Object.entries(derived.rp).map(([key, value]) => ({ key, value }))
      : [];

  const searchableText = [
    ...rpPairs.map((p) => `${String(p.key).toLowerCase()}=${String(p.value).toLowerCase()}`),
    ...rawPairs.map((p) => `${String(p.key).toLowerCase()}=${String(p.value).toLowerCase()}`),
    `lobby=${String(derived.lobbyRaw || "").toLowerCase()}`,
    `appid=${String(data.appid || "").toLowerCase()}`,
  ].join(" | ");

  return {
    steamid64: data.steamid64,
    persona_state: data.persona_state,
    appid: data.appid,
    in_game_flag: data.in_game,
    last_updated: data.last_updated,
    derived: {
      in_game: derived.inGame,
      in_match: derived.inMatch,
      in_demo: derived.demo,
      in_bot_match: derived.inBotMatch,
      in_custom_game: derived.inCustomGame,
      lobby_info: derived.lobbyRaw || "",
      game_mode: derived.gameModeRaw || null,
      game_mode_label: derived.gameModeLabel || null,
      match_id: derived.matchId || null,
      hero_token: derived.heroToken || null,
      hero_name: derived.heroName || null,
      hero_level: derived.heroLevel ?? null,
      match_seconds: derived.matchSeconds ?? null,
      match_time: derived.matchTime ?? null,
    },
    rich_presence_object: derived.rp,
    rich_presence_pairs: rpPairs,
    rich_presence_raw_pairs: rawPairs,
    searchable_text: searchableText,
  };
}

function createSession({ bridgeId, userId, login, password, sharedSecret, isDefault }) {
  const client = new SteamUser();
  const presence = new Map();
  const matchStart = new Map();

  const session = {
    bridgeId: String(bridgeId),
    userId: Number(userId),
    client,
    presence,
    matchStart,
    loggedOn: false,
    lastError: null,
    lastSeen: null,
    refreshTimer: null,
  };

  client.on("loggedOn", () => {
    session.loggedOn = true;
    session.lastError = null;
    session.lastSeen = Date.now();
    console.log(`[bridge] Logged into Steam (bridge=${session.bridgeId}, user=${session.userId})`);
    client.setPersona(SteamUser.EPersonaState.Online);
  });

  client.on("error", (err) => {
    session.loggedOn = false;
    session.lastError = String(err?.message || err);
    console.error(`[bridge] Steam error (bridge=${session.bridgeId})`, err);
  });

  client.on("disconnected", () => {
    session.loggedOn = false;
    console.warn(`[bridge] Steam disconnected (bridge=${session.bridgeId})`);
  });

  client.on("friendsList", () => {
    for (const steamid of Object.keys(client.myFriends || {})) {
      client.getPersonas([steamid]);
    }
  });

  client.on("user", (sid, user) => {
    const id64 = sid.getSteamID64();
    const previous = presence.get(id64);

    let rpRaw = user.rich_presence || {};
    if (Array.isArray(rpRaw) && rpRaw.length === 0 && previous) {
      rpRaw = previous.rich_presence_raw || rpRaw;
    }

    const rp = Array.isArray(rpRaw)
      ? Object.fromEntries(rpRaw.map((entry) => [entry.key, entry.value]))
      : rpRaw;

    presence.set(id64, {
      steamid64: id64,
      persona_state: user.persona_state,
      appid: user.gameid || null,
      in_game: !!user.gameid,
      rich_presence: rp,
      rich_presence_raw: rpRaw,
      last_updated: Date.now(),
    });
    session.lastSeen = Date.now();
  });

  session.refreshTimer = setInterval(() => {
    if (!session.loggedOn) return;
    const ids = Object.keys(client.myFriends || {});
    if (ids.length) {
      client.getPersonas(ids);
    }
  }, 30000);

  const details = { accountName: login, password: password };
  if (sharedSecret) {
    details.twoFactorCode = SteamTotp.getAuthCode(sharedSecret);
  }
  client.logOn(details);

  if (isDefault) {
    defaultBridgeByUser.set(String(userId), String(bridgeId));
  }

  return session;
}

function stopSession(bridgeId) {
  const key = String(bridgeId);
  const session = sessions.get(key);
  if (!session) return;
  if (session.refreshTimer) clearInterval(session.refreshTimer);
  try {
    session.client.removeAllListeners();
    session.client.logOff();
  } catch (_) {
    // ignore
  }
  sessions.delete(key);
}

function getSessionFor(userId, bridgeId) {
  if (bridgeId && sessions.has(String(bridgeId))) {
    return sessions.get(String(bridgeId));
  }
  if (userId !== undefined && userId !== null) {
    const defaultId = defaultBridgeByUser.get(String(userId));
    if (defaultId && sessions.has(defaultId)) {
      return sessions.get(defaultId);
    }
    for (const session of sessions.values()) {
      if (session.userId === Number(userId)) return session;
    }
  }
  return null;
}

function statusForSession(session) {
  if (!session) return { status: "offline" };
  if (session.loggedOn) return { status: "online" };
  if (session.lastError) return { status: "error", last_error: session.lastError };
  return { status: "connecting" };
}

app.get("/health", (_req, res) => {
  const anyOnline = Array.from(sessions.values()).some((session) => session.loggedOn);
  res.json({ status: anyOnline ? "ok" : "down", loggedOn: anyOnline });
});

app.post("/internal/bridge/:bridgeId/connect", (req, res) => {
  const bridgeId = req.params.bridgeId;
  const { user_id, login, password, shared_secret, is_default } = req.body || {};
  if (!user_id || !login || !password) {
    return res.status(400).json({ error: "missing_fields" });
  }
  stopSession(bridgeId);
  const session = createSession({
    bridgeId,
    userId: Number(user_id),
    login,
    password,
    sharedSecret: shared_secret || null,
    isDefault: Boolean(is_default),
  });
  sessions.set(String(bridgeId), session);
  res.json({
    ok: true,
    bridge_id: String(bridgeId),
    user_id: Number(user_id),
    ...statusForSession(session),
  });
});

app.post("/internal/bridge/:bridgeId/disconnect", (req, res) => {
  const bridgeId = req.params.bridgeId;
  const { user_id } = req.body || {};
  stopSession(bridgeId);
  if (user_id !== undefined && user_id !== null) {
    const defaultId = defaultBridgeByUser.get(String(user_id));
    if (defaultId === String(bridgeId)) {
      defaultBridgeByUser.delete(String(user_id));
    }
  }
  res.json({ ok: true, bridge_id: String(bridgeId) });
});

app.get("/internal/bridge/:bridgeId/status", (req, res) => {
  const bridgeId = req.params.bridgeId;
  const session = sessions.get(String(bridgeId));
  if (!session) return res.status(404).json({ error: "bridge_not_found" });
  const status = statusForSession(session);
  res.json({
    bridge_id: String(bridgeId),
    user_id: session.userId,
    logged_on: !!session.loggedOn,
    last_error: session.lastError,
    last_seen: session.lastSeen,
    ...status,
  });
});

app.get("/internal/bridge/user/:userId", (req, res) => {
  const userId = Number(req.params.userId);
  const items = [];
  for (const session of sessions.values()) {
    if (session.userId !== userId) continue;
    const status = statusForSession(session);
    items.push({
      bridge_id: session.bridgeId,
      user_id: session.userId,
      logged_on: !!session.loggedOn,
      last_error: session.lastError,
      last_seen: session.lastSeen,
      ...status,
    });
  }
  res.json({ items });
});

app.get("/presence/:steamid", (req, res) => {
  const sid = req.params.steamid;
  const userId = req.query.user_id ? Number(req.query.user_id) : null;
  const bridgeId = req.query.bridge_id ? String(req.query.bridge_id) : null;
  const session = getSessionFor(userId, bridgeId);
  if (!session) return res.status(404).json({ error: "bridge_not_found" });
  const data = session.presence.get(sid);
  if (!data) return res.status(404).json({ error: "not_found" });

  const derived = derivePresence(data, session.matchStart);

  res.json({
    in_game: derived.inGame,
    in_match: derived.inMatch,
    in_demo: derived.demo,
    in_bot_match: derived.inBotMatch,
    in_custom_game: derived.inCustomGame,
    lobby_info: derived.lobbyRaw || "",
    game_mode: derived.gameModeRaw || null,
    game_mode_label: derived.gameModeLabel || null,
    hero_token: derived.heroToken || null,
    hero_name: derived.heroName || null,
    hero_level: derived.heroLevel ?? null,
    match_seconds: derived.matchSeconds ?? null,
    match_time: derived.matchTime ?? null,
    last_updated: data.last_updated,
    derived: {
      in_game: derived.inGame,
      in_match: derived.inMatch,
      in_demo: derived.demo,
      in_bot_match: derived.inBotMatch,
      in_custom_game: derived.inCustomGame,
    },
  });
});

app.get("/presencefull/:steamid", (req, res) => {
  const userId = req.query.user_id ? Number(req.query.user_id) : null;
  const bridgeId = req.query.bridge_id ? String(req.query.bridge_id) : null;
  const session = getSessionFor(userId, bridgeId);
  if (!session) return res.status(404).json({ error: "bridge_not_found" });

  const sid = req.params.steamid;
  const data = session.presence.get(sid);
  if (!data) return res.status(404).json({ error: "not_found" });

  const derived = derivePresence(data, session.matchStart);

  res.json({
    ...data,
    derived: {
      in_game: derived.inGame,
      in_match: derived.inMatch,
      in_demo: derived.demo,
      in_bot_match: derived.inBotMatch,
      in_custom_game: derived.inCustomGame,
      lobby_info: derived.lobbyRaw || "",
      game_mode: derived.gameModeRaw || null,
      game_mode_label: derived.gameModeLabel || null,
      match_id: derived.matchId ?? null,
      hero_token: derived.heroToken || null,
      hero_name: derived.heroName || null,
      hero_level: derived.heroLevel ?? null,
      match_seconds: derived.matchSeconds ?? null,
      match_time: derived.matchTime ?? null,
    },
  });
});

app.get("/debug/presence/:steamid", requireDebugToken, (req, res) => {
  const userId = req.query.user_id ? Number(req.query.user_id) : null;
  const bridgeId = req.query.bridge_id ? String(req.query.bridge_id) : null;
  const session = getSessionFor(userId, bridgeId);
  if (!session) return res.status(404).json({ error: "bridge_not_found" });
  const sid = req.params.steamid;
  const data = session.presence.get(sid);
  if (!data) return res.status(404).json({ error: "not_found" });

  res.json(buildDebugView(data, session.matchStart));
});

app.get("/debug/keys", requireDebugToken, (req, res) => {
  const userId = req.query.user_id ? Number(req.query.user_id) : null;
  const bridgeId = req.query.bridge_id ? String(req.query.bridge_id) : null;
  const session = getSessionFor(userId, bridgeId);
  if (!session) return res.status(404).json({ error: "bridge_not_found" });
  res.json({
    count: session.presence.size,
    steamids: Array.from(session.presence.keys()).slice(0, 500),
  });
});

const port = process.env.PORT || 4000;
app.listen(port, () => console.log(`[bridge] listening on ${port}`));
