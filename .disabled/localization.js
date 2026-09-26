const LANGUAGE_CONFIG = {
  en: {
    title: "✨ Generate Story",
    story_title: "Story Title",
    premise: "Premise",
    characters: "Characters (comma-separated)",
    tone: "Tone",
    generate: "Generate Story",
    publish: "Publish",
    save_draft: "Save Draft",
    narrate: "Narrate",
    copy: "Copy",
    cancel: "Cancel",
    language_select: "Select Language",
    generating: "Generating story with AURA AI...",
    preview: "Preview",
    settings: "Settings",
    help: "Help",
    status: "Status",
    backend: "Backend",
    drafts_saved: "Drafts Saved",
    recent_drafts: "Recent Drafts",
    no_drafts: "No drafts yet",
    online: "Online",
    offline: "Offline",
    error: "Error",
  },
  es: {
    title: "✨ Generar Historia",
    story_title: "Título de la Historia",
    premise: "Premisa",
    characters: "Personajes (separados por comas)",
    tone: "Tono",
    generate: "Generar Historia",
    publish: "Publicar",
    save_draft: "Guardar Borrador",
    narrate: "Narrar",
    copy: "Copiar",
    cancel: "Cancelar",
    language_select: "Seleccionar Idioma",
    generating: "Generando historia con AURA AI...",
    preview: "Vista previa",
    settings: "Ajustes",
    help: "Ayuda",
    status: "Estado",
    backend: "Backend",
    drafts_saved: "Borradores Guardados",
    recent_drafts: "Borradores Recientes",
    no_drafts: "Sin borradores",
    online: "En línea",
    offline: "Desconectado",
    error: "Error",
  },
  fr: {
    title: "✨ Générer une Histoire",
    story_title: "Titre de l'Histoire",
    premise: "Prémisse",
    characters: "Personnages (séparés par des virgules)",
    tone: "Ton",
    generate: "Générer une Histoire",
    publish: "Publier",
    save_draft: "Enregistrer",
    narrate: "Narrer",
    copy: "Copier",
    cancel: "Annuler",
    language_select: "Sélectionner la Langue",
    generating: "Génération d'histoire avec AURA AI...",
    preview: "Aperçu",
    settings: "Paramètres",
    help: "Aide",
    status: "Statut",
    backend: "Backend",
    drafts_saved: "Brouillons Enregistrés",
    recent_drafts: "Brouillons Récents",
    no_drafts: "Pas de brouillons",
    online: "En ligne",
    offline: "Hors ligne",
    error: "Erreur",
  },
  de: {
    title: "✨ Geschichte Generieren",
    story_title: "Geschichtstitel",
    premise: "Prämisse",
    characters: "Charaktere (durch Kommas getrennt)",
    tone: "Ton",
    generate: "Geschichte Generieren",
    publish: "Veröffentlichen",
    save_draft: "Entwurf Speichern",
    narrate: "Erzählen",
    copy: "Kopieren",
    cancel: "Abbrechen",
    language_select: "Sprache Wählen",
    generating: " Geschichte wird mit AURA AI generiert...",
    preview: "Vorschau",
    settings: "Einstellungen",
    help: "Hilfe",
    status: "Status",
    backend: "Backend",
    drafts_saved: "Entwürfe Gespeichert",
    recent_drafts: "Letzte Entwürfe",
    no_drafts: "Keine Entwürfe",
    online: "Online",
    offline: "Offline",
    error: "Fehler",
  },
  pt: {
    title: "✨ Gerar História",
    story_title: "Título da História",
    premise: "Premissa",
    characters: "Personagens (separados por vírgulas)",
    tone: "Tom",
    generate: "Gerar História",
    publish: "Publicar",
    save_draft: "Salvar Rascunho",
    narrate: "Narrar",
    copy: "Copiar",
    cancel: "Cancelar",
    language_select: "Selecionar Idioma",
    generating: "Gerando história com AURA AI...",
    preview: "Pré-visualização",
    settings: "Configurações",
    help: "Ajuda",
    status: "Status",
    backend: "Backend",
    drafts_saved: "Rascunhos Salvos",
    recent_drafts: "Rascunhos Recentes",
    no_drafts: "Sem rascunhos",
    online: "Online",
    offline: "Offline",
    error: "Erro",
  },
  ja: {
    title: "✨ ストーリーを生成",
    story_title: "ストーリータイトル",
    premise: "前提",
    characters: "キャラクター（カンマ区切り）",
    tone: "トーン",
    generate: "ストーリーを生成",
    publish: "公開",
    save_draft: "下書き保存",
    narrate: "読み上げ",
    copy: "コピー",
    cancel: "キャンセル",
    language_select: "言語を選択",
    generating: "AURA AIでストーリーを生成中...",
    preview: "プレビュー",
    settings: "設定",
    help: "ヘルプ",
    status: "ステータス",
    backend: "バックエンド",
    drafts_saved: "下書き保存済み",
    recent_drafts: "最近の下書き",
    no_drafts: "下書きなし",
    online: "オンライン",
    offline: "オフライン",
    error: "エラー",
  },
  "zh-cn": {
    title: "✨ 生成故事",
    story_title: "故事标题",
    premise: "前提",
    characters: "人物（用逗号分隔）",
    tone: "语气",
    generate: "生成故事",
    publish: "发布",
    save_draft: "保存草稿",
    narrate: "朗读",
    copy: "复制",
    cancel: "取消",
    language_select: "选择语言",
    generating: "正在用AURA AI生成故事...",
    preview: "预览",
    settings: "设置",
    help: "帮助",
    status: "状态",
    backend: "后端",
    drafts_saved: "已保存草稿",
    recent_drafts: "最近草稿",
    no_drafts: "暂无草稿",
    online: "在线",
    offline: "离线",
    error: "错误",
  },
};

class ExtensionLocalizer {
  constructor() {
    this.currentLanguage = this.detectExtensionLanguage();
  }

  detectExtensionLanguage() {
    let lang = (navigator.language || 'en').split('-')[0];
    if (!LANGUAGE_CONFIG[lang]) {
      lang = 'en';
    }
    localStorage.setItem('aura_extension_lang', lang);
    return lang;
  }

  setLanguage(langCode) {
    if (LANGUAGE_CONFIG[langCode]) {
      this.currentLanguage = langCode;
      localStorage.setItem('aura_extension_lang', langCode);
      location.reload();
    }
  }

  translate(key) {
    return LANGUAGE_CONFIG[this.currentLanguage]?.[key] || `[${key}]`;
  }

  applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach((element) => {
      const key = element.getAttribute('data-i18n');
      element.textContent = this.translate(key);
    });
  }
}

const localizer = new ExtensionLocalizer();
