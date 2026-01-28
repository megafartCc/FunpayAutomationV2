/* eslint-disable no-console */
/**
 * Resolves FunPay categories by scraping logged-in pages.
 * Run in the browser console on funpay.com (must be authenticated).
 */
(async () => {
  const urls = ["/en/lots/", "/lots/", "/en/", "/"];
  const seen = new Map(); // id -> payload

  const normalizeText = (value, fallback = "") =>
    (value || fallback).toString().trim();

  const addCategory = (id, payload) => {
    if (!seen.has(id)) {
      seen.set(id, payload);
    }
  };

  const parse = (html) => {
    const doc = new DOMParser().parseFromString(html, "text/html");

    // primary: structured grid
    doc.querySelectorAll(".promo-game-item").forEach((block) => {
      const gameEl = block.querySelector(".game-title a, .game-title");
      const gameName = normalizeText(gameEl?.textContent, "Unknown game");

      const serverLabels = {};
      block.querySelectorAll("button[data-id]").forEach((btn) => {
        const id = normalizeText(btn.getAttribute("data-id"));
        if (id) {
          serverLabels[id] = normalizeText(btn.textContent);
        }
      });

      block.querySelectorAll("ul.list-inline[data-id]").forEach((ul) => {
        const dataId = normalizeText(ul.getAttribute("data-id"));
        const server = serverLabels[dataId] || "";
        const gameLabel = server ? `${gameName} (${server})` : gameName;

        ul.querySelectorAll("a[href*='/lots/']").forEach((a) => {
          const match = a.getAttribute("href")?.match(/\/lots\/(\d+)/);
          if (!match) return;
          const id = Number(match[1]);
          if (!Number.isFinite(id)) return;
          const category = normalizeText(a.textContent, `Category ${id}`);

          addCategory(id, {
            id,
            name: `${gameLabel} - ${category}`,
            game: gameLabel,
            category,
            server: server || null,
          });
        });
      });
    });

    // fallback: any stray links
    doc.querySelectorAll("a[href*='/lots/']").forEach((a) => {
      const match = a.getAttribute("href")?.match(/\/lots\/(\d+)/);
      if (!match) return;
      const id = Number(match[1]);
      if (!Number.isFinite(id) || seen.has(id)) return;

      const category = normalizeText(a.textContent, `Category ${id}`);
      let gameLabel = "Unknown game";
      const block = a.closest(".promo-game-item");
      if (block) {
        const gEl = block.querySelector(".game-title a, .game-title");
        gameLabel = normalizeText(gEl?.textContent, gameLabel);
      }

      addCategory(id, {
        id,
        name: `${gameLabel} - ${category}`,
        game: gameLabel,
        category,
        server: null,
      });
    });
  };

  for (const path of urls) {
    try {
      const response = await fetch(path, { credentials: "include" });
      if (!response.ok) {
        console.warn("Fetch failed", path, response.status);
        continue;
      }
      const html = await response.text();
      parse(html);
    } catch (error) {
      console.warn("Fetch failed", path, error);
    }
  }

  // prune bare game-only rows if detailed categories exist for that game
  const gamesWithCats = new Set(
    [...seen.values()]
      .filter((value) => value.category && value.game)
      .map((value) => normalizeText(value.game)),
  );
  for (const [id, value] of seen.entries()) {
    const gameName = normalizeText(value.game);
    if (gamesWithCats.has(gameName) && (!value.category || value.category === value.name)) {
      seen.delete(id);
    }
  }

  const rows = [...seen.values()].sort(
    (a, b) =>
      normalizeText(a.game).localeCompare(normalizeText(b.game)) ||
      normalizeText(a.category || a.name).localeCompare(normalizeText(b.category || b.name)) ||
      a.id - b.id,
  );

  console.table(rows);
  console.log("Total categories:", rows.length);
})();
