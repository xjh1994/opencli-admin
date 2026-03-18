import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import zh from './zh'
import en from './en'

const saved = localStorage.getItem('lang') ?? 'zh'

i18n.use(initReactI18next).init({
  resources: {
    zh: { translation: zh },
    en: { translation: en },
  },
  lng: saved,
  fallbackLng: 'zh',
  interpolation: { escapeValue: false },
})

export default i18n
