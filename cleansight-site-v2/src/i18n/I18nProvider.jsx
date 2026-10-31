import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import vi from './vi.js';
import en from './en.js';

const DICTS = { vi, en };
const STORAGE_KEY = 'cleansight.lang';

function readStored() {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return v === 'vi' || v === 'en' ? v : null;
  } catch {
    return null;
  }
}

function writeStored(lang) {
  try {
    window.localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    /* storage unavailable (private mode, blocked): the choice simply is not remembered */
  }
}

/** Default language: a stored choice wins; otherwise any `vi*` entry in the browser list → vi, else en. */
export function detectLanguage() {
  const stored = readStored();
  if (stored) return stored;
  const list =
    typeof navigator !== 'undefined'
      ? (navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || ''])
      : [];
  return list.some((l) => typeof l === 'string' && l.toLowerCase().startsWith('vi')) ? 'vi' : 'en';
}

function lookup(dict, key) {
  return key.split('.').reduce((node, part) => (node == null ? undefined : node[part]), dict);
}

const I18nContext = createContext(null);

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(detectLanguage);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((next) => {
    if (next !== 'vi' && next !== 'en') return;
    setLangState(next);
    writeStored(next);
  }, []);

  const t = useCallback(
    (key) => {
      const value = lookup(DICTS[lang], key);
      if (value === undefined) {
        if (import.meta.env.DEV) console.warn(`[i18n] missing key "${key}" for "${lang}"`);
        return key;
      }
      return value;
    },
    [lang],
  );

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used inside <I18nProvider>');
  return ctx;
}
