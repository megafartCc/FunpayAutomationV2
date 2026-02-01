import React, { createContext, useContext, useEffect, useMemo, useState } from "react";

export type ThemeMode = "light" | "dark";
export type LanguageCode = "en" | "ru";

type PreferencesContextValue = {
  theme: ThemeMode;
  language: LanguageCode;
  setTheme: (theme: ThemeMode) => void;
  setLanguage: (language: LanguageCode) => void;
};

const PreferencesContext = createContext<PreferencesContextValue | null>(null);

const STORAGE_KEY = "funpay.preferences";

const getInitialPreferences = (): { theme: ThemeMode; language: LanguageCode } => {
  if (typeof window === "undefined") {
    return { theme: "light", language: "ru" };
  }
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored) as Partial<{ theme: ThemeMode; language: LanguageCode }>;
      const theme = parsed.theme === "dark" || parsed.theme === "light" ? parsed.theme : undefined;
      const language = parsed.language === "ru" || parsed.language === "en" ? parsed.language : undefined;
      if (theme && language) return { theme, language };
      if (theme) return { theme, language: language || "ru" };
      if (language) return { theme: "light", language };
    }
  } catch {
    // ignore storage errors
  }
  const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  return { theme: prefersDark ? "dark" : "light", language: "ru" };
};

export const PreferencesProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const initial = useMemo(() => getInitialPreferences(), []);
  const [theme, setTheme] = useState<ThemeMode>(initial.theme);
  const [language, setLanguage] = useState<LanguageCode>(initial.language);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    root.lang = language;
    root.style.colorScheme = theme;
  }, [theme, language]);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ theme, language }));
    } catch {
      // ignore storage errors
    }
  }, [theme, language]);

  const value = useMemo(
    () => ({
      theme,
      language,
      setTheme,
      setLanguage,
    }),
    [theme, language],
  );

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
};

export const usePreferences = () => {
  const context = useContext(PreferencesContext);
  if (!context) {
    throw new Error("usePreferences must be used within PreferencesProvider");
  }
  return context;
};
