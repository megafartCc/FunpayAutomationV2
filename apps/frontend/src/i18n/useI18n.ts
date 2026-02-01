import { useCallback, useMemo } from "react";
import { usePreferences } from "../context/PreferencesContext";
import { translations, TranslationKey } from "./translations";

type TemplateVars = Record<string, string | number>;

const applyTemplate = (value: string, vars?: TemplateVars) => {
  if (!vars) return value;
  return value.replace(/\{(\w+)\}/g, (_match, key) => String(vars[key] ?? ""));
};

export const useI18n = () => {
  const { language } = usePreferences();
  const dictionary = useMemo(() => translations[language] ?? translations.en, [language]);

  const t = useCallback(
    (key: TranslationKey, vars?: TemplateVars) => {
      const raw = dictionary[key] ?? translations.en[key] ?? key;
      return applyTemplate(raw, vars);
    },
    [dictionary],
  );

  const tr = useCallback(
    (en: string, ru: string, vars?: TemplateVars) => {
      const raw = language === "ru" ? ru : en;
      return applyTemplate(raw, vars);
    },
    [language],
  );

  return { t, tr, language };
};
