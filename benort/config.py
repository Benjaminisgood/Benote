"""项目级配置常量与初始化辅助函数。"""

import os
import textwrap


DEFAULT_PROJECT_NAME = "default"
# 默认模板文件名，可根据需要在 temps 中新增不同方案
DEFAULT_TEMPLATE_FILENAME = "base_template.yaml"
DEFAULT_MARKDOWN_TEMPLATE_FILENAME = "markdown_default.yaml"

# 若项目未定制模板，使用该结构作为兜底的 LaTeX 片段
FALLBACK_TEMPLATE: dict[str, str] = {
    "header": textwrap.dedent(
        r"""
        \documentclass{beamer}
        \usetheme{Madrid}
        \usecolortheme{seahorse}
        \usepackage{graphicx}
        \usepackage{hyperref}
        \usepackage{booktabs}
        \usepackage{amsmath, amssymb}
        \usepackage{fontspec}
        \usepackage{mwe}
        \usepackage{xeCJK}
        \setCJKmainfont{PingFang SC}
        \setsansfont{PingFang SC}
        \setmainfont{PingFang SC}
        \graphicspath{{.}{images/}{../images/}{../attachments/}{../}}
        \makeatletter
        \newcommand{\img}[2][]{
          \IfFileExists{#2}{\includegraphics[#1]{#2}}{
            \typeout{[warn] Missing image #2, using placeholder}
            \includegraphics[#1]{example-image}
          }
        }
        \makeatother
        \usepackage[backend=bibtex,style=chem-acs,maxnames=6,giveninits=true,articletitle=true]{biblatex}
        \addbibresource{refs.bib}
        \setbeameroption{show notes}
        \title{report}
        \author{Ben}
        """
    ).strip(),
    "beforePages": "\\begin{document}",
    "footer": "\\end{document}",
}

# Markdown 预览默认样式配置
FALLBACK_MARKDOWN_TEMPLATE: dict[str, str] = {
    "css": textwrap.dedent(
        """
        :root {
          color-scheme: light;
        }
        .markdown-note {
          font-family: "Helvetica Neue", Arial, "PingFang SC", sans-serif;
          font-size: 16px;
          line-height: 1.65;
          color: #1f2933;
        }
        .markdown-note h1,
        .markdown-note h2,
        .markdown-note h3 {
          font-weight: 600;
          margin-top: 1.6em;
          margin-bottom: 0.6em;
          line-height: 1.3;
        }
        .markdown-note h1 {
          font-size: 2.1em;
        }
        .markdown-note h2 {
          font-size: 1.7em;
        }
        .markdown-note h3 {
          font-size: 1.35em;
        }
        .markdown-note p {
          margin-bottom: 0.9em;
        }
        .markdown-note ul,
        .markdown-note ol {
          padding-left: 1.4em;
          margin-bottom: 1em;
        }
        .markdown-note blockquote {
          border-left: 4px solid #8ea1c7;
          color: #4b5563;
          background: #f7f9fc;
          margin: 1.2em 0;
          padding: 0.8em 1.1em;
          border-radius: 0.25rem;
        }
        .markdown-note code {
          font-family: "SFMono-Regular", Menlo, Consolas, "Liberation Mono", monospace;
          background: #f1f5f9;
          padding: 0.1em 0.35em;
          border-radius: 0.25rem;
          font-size: 0.95em;
        }
        .markdown-note pre code {
          display: block;
          padding: 0;
          background: transparent;
          font-size: 0.95em;
        }
        .markdown-note pre {
          background: #0f172a;
          color: #e2e8f0;
          padding: 1em;
          border-radius: 0.5rem;
          overflow-x: auto;
        }
        .markdown-note img {
          max-width: min(100%, 720px);
          height: auto;
          display: block;
          margin: 1.25rem auto;
          border-radius: 0.75rem;
          box-shadow: 0 18px 40px rgba(15, 23, 42, 0.18);
          cursor: zoom-in;
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .markdown-note img:hover {
          transform: translateY(-2px) scale(1.01);
          box-shadow: 0 24px 55px rgba(15, 23, 42, 0.24);
        }
        .markdown-note img:focus {
          outline: 3px solid rgba(59, 130, 246, 0.45);
          outline-offset: 4px;
        }
        .markdown-note figure {
          margin: 1.5rem auto;
          text-align: center;
        }
        .markdown-note figcaption {
          margin-top: 0.75rem;
          font-size: 0.9rem;
          color: #6b7280;
        }
        .markdown-note .markdown-preview-table-wrapper {
          position: relative;
          margin: 1.25rem 0;
          border: 1px solid #c0ccf4;
          border-radius: 0.9rem;
          background: rgba(241, 244, 255, 0.94);
          overflow: auto;
          max-width: 100%;
          max-height: clamp(320px, 58vh, 640px);
          box-shadow: 0 18px 42px rgba(15, 23, 42, 0.18);
          padding: 1.75rem 1rem 1.4rem;
        }
        .markdown-note .markdown-preview-table-wrapper table {
          width: 100%;
          min-width: 100%;
          border-collapse: collapse;
          background: rgba(235, 239, 255, 0.96);
          table-layout: auto;
        }
        .markdown-note .markdown-preview-table-wrapper caption {
          caption-side: top;
          text-align: left;
          font-weight: 600;
          margin-bottom: 0.75rem;
          color: #1f2937;
        }
        .markdown-note .markdown-preview-table-wrapper thead th {
          position: sticky;
          top: 0;
          z-index: 5;
          background: rgba(210, 219, 255, 0.98);
          color: #111827;
          box-shadow: inset 0 -1px 0 rgba(131, 146, 199, 0.45);
        }
        .markdown-note .markdown-preview-table-wrapper tbody tr:nth-child(odd) {
          background: rgba(206, 214, 255, 0.58);
        }
        .markdown-note .markdown-preview-table-wrapper th,
        .markdown-note .markdown-preview-table-wrapper td {
          border: 1px solid rgba(138, 151, 199, 0.45);
          padding: 0.6rem 0.75rem;
          text-align: left;
          vertical-align: middle;
          word-break: break-word;
          white-space: normal;
        }
        .markdown-note .markdown-table-expand-btn {
          position: absolute;
          top: 0.75rem;
          right: 0.75rem;
          z-index: 10;
          display: inline-flex;
          align-items: center;
          gap: 0.35rem;
          padding: 0.3rem 0.75rem;
          font-size: 0.8rem;
          font-weight: 600;
          background: rgba(99, 102, 241, 0.12);
          border: 1px solid rgba(99, 102, 241, 0.35);
          border-radius: 999px;
          color: #3730a3;
          cursor: pointer;
        }
        .markdown-note .markdown-table-expand-btn:hover,
        .markdown-note .markdown-table-expand-btn:focus {
          background: rgba(99, 102, 241, 0.22);
          border-color: rgba(67, 56, 202, 0.55);
          color: #1e1b4b;
          outline: none;
        }
        .markdown-note table {
          width: 100%;
          border-collapse: collapse;
          margin: 1.4em 0;
        }
        .markdown-note th,
        .markdown-note td {
          border: 1px solid #cbd5f5;
          padding: 0.65em 0.75em;
        }
        .markdown-note th {
          background: #e6ecfe;
          font-weight: 600;
        }
        .markdown-note hr {
          border: none;
          border-top: 1px solid #d8e3f8;
          margin: 2em 0;
        }
        .markdown-note .markdown-callout {
          position: relative;
          border-radius: 0.9rem;
          padding: 1.05rem 1.25rem;
          margin: 1.4rem 0;
          border: 1px solid rgba(99, 102, 241, 0.22);
          background: rgba(99, 102, 241, 0.06);
          box-shadow: 0 18px 42px rgba(15, 23, 42, 0.14);
        }
        .markdown-note .markdown-callout + .markdown-callout {
          margin-top: 1.15rem;
        }
        .markdown-note .markdown-callout-title {
          font-weight: 600;
          margin-bottom: 0.45rem;
          letter-spacing: 0.02em;
          color: #312e81;
        }
        .markdown-note .markdown-callout-body > :first-child {
          margin-top: 0;
        }
        .markdown-note .markdown-callout-body > :last-child {
          margin-bottom: 0;
        }
        .markdown-note .markdown-callout.info {
          border-color: rgba(59, 130, 246, 0.35);
          background: rgba(59, 130, 246, 0.1);
        }
        .markdown-note .markdown-callout.info .markdown-callout-title {
          color: #1d4ed8;
        }
        .markdown-note .markdown-callout.tip {
          border-color: rgba(16, 185, 129, 0.35);
          background: rgba(16, 185, 129, 0.1);
        }
        .markdown-note .markdown-callout.tip .markdown-callout-title {
          color: #047857;
        }
        .markdown-note .markdown-callout.warning {
          border-color: rgba(251, 191, 36, 0.55);
          background: rgba(251, 191, 36, 0.14);
        }
        .markdown-note .markdown-callout.warning .markdown-callout-title {
          color: #92400e;
        }
        body.theme-dark .markdown-note .markdown-callout {
          border-color: rgba(99, 102, 241, 0.35);
          background: rgba(15, 23, 42, 0.82);
          box-shadow: 0 24px 60px rgba(2, 6, 23, 0.55);
        }
        body.theme-dark .markdown-note .markdown-callout-title {
          color: #e0e7ff;
        }
        body.theme-dark .markdown-note .markdown-callout.info {
          border-color: rgba(96, 165, 250, 0.45);
          background: rgba(37, 99, 235, 0.24);
        }
        body.theme-dark .markdown-note .markdown-callout.tip {
          border-color: rgba(45, 212, 191, 0.45);
          background: rgba(16, 185, 129, 0.26);
        }
        body.theme-dark .markdown-note .markdown-callout.warning {
          border-color: rgba(251, 191, 36, 0.55);
          background: rgba(202, 138, 4, 0.32);
        }
        body.theme-dark .markdown-note .markdown-callout.warning .markdown-callout-title {
          color: #fde68a;
        }
        """
    ).strip(),
    "wrapperClass": "markdown-note",
}

# OpenAI ChatCompletion / Embedding / TTS 相关配置（支持分用途 env）
OPENAI_API_BASE_URL = os.environ.get("OPENAI_API_BASE_URL", "https://api.openai.com/v1")
OPENAI_CHAT_COMPLETIONS_MODEL = os.environ.get("LLM_CHAT_MODEL", os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o"))
OPENAI_CHAT_PATH = os.environ.get("LLM_CHAT_PATH", os.environ.get("OPENAI_CHAT_PATH", "/chat/completions"))
DEFAULT_EMBEDDING_MODEL = os.environ.get("LLM_EMBEDDING_MODEL", os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"))
DEFAULT_EMBEDDING_PATH = os.environ.get("LLM_EMBEDDING_PATH", "/embeddings")
DEFAULT_TTS_MODEL = os.environ.get("LLM_TTS_MODEL", os.environ.get("OPENAI_TTS_MODEL", "tts-1"))
DEFAULT_TTS_PATH = os.environ.get("LLM_TTS_PATH", "/audio/speech")
DEFAULT_CHAT_BASE_URL = os.environ.get("LLM_CHAT_BASE_URL", OPENAI_API_BASE_URL)
DEFAULT_EMBEDDING_BASE_URL = os.environ.get("LLM_EMBEDDING_BASE_URL", OPENAI_API_BASE_URL)
DEFAULT_TTS_BASE_URL = os.environ.get("LLM_TTS_BASE_URL", OPENAI_API_BASE_URL)

# ChatAnywhere ChatCompletion 相关配置（保持兼容但可被 LLM_* 覆盖）
CHATANYWHERE_API_BASE_URL = os.environ.get("CHAT_ANYWHERE_BASE_URL", "https://api.chatanywhere.tech/v1")
CHATANYWHERE_CHAT_PATH = os.environ.get("CHAT_ANYWHERE_CHAT_PATH", "/chat/completions")
CHATANYWHERE_DEFAULT_MODEL = os.environ.get("CHAT_ANYWHERE_MODEL", "gpt-4o")
CHATANYWHERE_EMBEDDING_MODEL = os.environ.get("CHAT_ANYWHERE_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
CHATANYWHERE_TTS_MODEL = os.environ.get("CHAT_ANYWHERE_TTS_MODEL", DEFAULT_TTS_MODEL)
CHATANYWHERE_EMBEDDING_PATH = os.environ.get("CHAT_ANYWHERE_EMBEDDING_PATH", DEFAULT_EMBEDDING_PATH)
CHATANYWHERE_TTS_PATH = os.environ.get("CHAT_ANYWHERE_TTS_PATH", DEFAULT_TTS_PATH)
CHATANYWHERE_EMBEDDING_BASE_URL = os.environ.get("CHAT_ANYWHERE_EMBEDDING_BASE_URL", CHATANYWHERE_API_BASE_URL)
CHATANYWHERE_TTS_BASE_URL = os.environ.get("CHAT_ANYWHERE_TTS_BASE_URL", CHATANYWHERE_API_BASE_URL)

# 通用 LLM 提供方注册表，便于统一管理聊天模型调用
LLM_PROVIDERS: dict[str, dict[str, object]] = {
    "openai": {
        "id": "openai",
        "label": "OpenAI",
        "base_url": DEFAULT_CHAT_BASE_URL,
        "chat_path": OPENAI_CHAT_PATH,
        "tts_path": DEFAULT_TTS_PATH,
        "embedding_path": DEFAULT_EMBEDDING_PATH,
        "embedding_base_url": DEFAULT_EMBEDDING_BASE_URL,
        "tts_base_url": DEFAULT_TTS_BASE_URL,
        "default_model": OPENAI_CHAT_COMPLETIONS_MODEL,
        "default_embedding_model": DEFAULT_EMBEDDING_MODEL,
        "default_tts_model": DEFAULT_TTS_MODEL,
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4.1",
            "gpt-4.1-mini",
            "o4-mini",
        ],
        "embedding_models": [
            "text-embedding-3-large",
            "text-embedding-3-small",
            "text-embedding-ada-002",
        ],
        "tts_models": [
            "tts-1",
            "tts-1-hd",
        ],
        "api_key_env": "OPENAI_API_KEY",
        "api_key_header": "Authorization",
        "api_key_prefix": "Bearer ",
        "extra_headers": {},
        "timeout": 60,
    },
    "chatanywhere": {
        "id": "chatanywhere",
        "label": "ChatAnywhere",
        "base_url": CHATANYWHERE_API_BASE_URL,
        "chat_path": CHATANYWHERE_CHAT_PATH,
        "tts_path": CHATANYWHERE_TTS_PATH,
        "embedding_path": CHATANYWHERE_EMBEDDING_PATH,
        "embedding_base_url": CHATANYWHERE_EMBEDDING_BASE_URL,
        "tts_base_url": CHATANYWHERE_TTS_BASE_URL,
        "default_model": CHATANYWHERE_DEFAULT_MODEL,
        "default_embedding_model": CHATANYWHERE_EMBEDDING_MODEL,
        "default_tts_model": CHATANYWHERE_TTS_MODEL,
        "models": [
            CHATANYWHERE_DEFAULT_MODEL,
        ],
        "embedding_models": [
            CHATANYWHERE_EMBEDDING_MODEL,
            "text-embedding-3-small",
        ],
        "tts_models": [
            CHATANYWHERE_TTS_MODEL,
        ],
        "api_key_env": "CHAT_ANYWHERE_API_KEY",
        "api_key_header": "Authorization",
        "api_key_prefix": "Bearer ",
        "extra_headers": {},
        "timeout": 60,
    },
}

_ENV_DEFAULT_PROVIDER = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
DEFAULT_LLM_PROVIDER = _ENV_DEFAULT_PROVIDER if _ENV_DEFAULT_PROVIDER in LLM_PROVIDERS else "openai"

# OpenAI 语音合成参数，可按需调整音色/格式/语速
OPENAI_TTS_MODEL = "tts-1"
OPENAI_TTS_VOICE = "alloy"
OPENAI_TTS_RESPONSE_FORMAT = "mp3"
OPENAI_TTS_SPEED = 1.0

# 不同优化场景对应的系统提示与用户模板
AI_PROMPTS = {
    "script": {
        "system": "你是一个幻灯片演讲稿写作专家，服从我的指示，返回优化后的讲稿文本。",
        "template": (
            "你是一个幻灯片演讲稿写作专家。选择合适的演讲风格，可以进行高级感的幽默和帮助演讲者学习英语。\n"
            "优化对应的讲稿，使其表达更清晰、逻辑更流畅、适合演讲，内容不要脱离幻灯片主题。\n"
            "你需要根据我的幻灯片内容（也就是beamer）生成讲稿，LaTeX页面内容如下：\n{latex}\n\n"
            "我的笔记也可以作为你的参考，笔记内容如下：\n{markdown}\n\n"
            "如果没有特别说明，无论原始内容是什么语言，默认输出语言是英文en。\n\n"
            "原始讲稿如下：\n{script}\n\n"
            "如果原始讲稿有内容，判断是我的要求还是讲稿内容，如果是内容，请返回优化后的英文版讲稿文本。\n"
            "演讲稿不带有任何latex和markdown语法，可以附上一些表情包以及演讲技巧提示。\n"
        ),
    },
    "note": {
        "system": "你是一个笔记写作专家，返回优化后的笔记（Markdown）。",
        "template": (
            "你是一个幻灯片笔记/摘要写作专家。\n"
            "生成或优化一份适合阅读和记录的笔记（Markdown格式），保留要点、关键结论和联系。\n"
            "一切数学公式或者代码请用Markdown的$包裹的数学表示法以及代码块格式表示。注意！markdown不被认为是代码！不要出现```markdown，我的笔记本来就是markdownown格式的。\n"
            "LaTeX页面内容如下：\n{latex}\n\n"
            "原始笔记如下：\n{markdown}\n\n"
            "“ # ”后面是markdownown的注释，也是我给你的一些指示要求。\n"
            "如果笔记有内容，请参考latex beamer的内容直接返回优化后的笔记文本，主要是en和cn，使用Markdown格式。\n"
            "如果原始笔记为空，则自动根据我的现有幻灯片内容（也就是Latexbeamer的内容）进行生成相关的笔记。\n"
            "输出内容的语言应该和我的笔记原始文本保持一致，语言保持一致！！！我的笔记原文是英文就输出英文，中文就输出中文！！！\n"
            "再次强调！不要做翻译的工作，不允许偷懒输出一样的内容，我给的原始笔记是英文就必须输出优化后的英文en版笔记，并且我首选就是全英文笔记。\n"
            "只要输出笔记内容，不要输出任何多余的内容。比如“```markdown、注释：” 这种的垃圾。\n"
        ),
    },
    "latex": {
        "system": (
            "你是一个LaTeX Beamer幻灯片专家，只能在当前模板允许的宏包和命令范围内工作。 "
            "禁止添加新的宏包、命令或依赖，确保生成的代码在现有模板下可直接编译。"
        ),
        "template": (
            "请优化以下LaTeX Beamer幻灯片页面内容(每一个%后面都是给你的一些指示）。你需要完成“%”给你的命令任务指示要求，用beamer输出完成的结果！\n"
            "使其更规范、简洁、美观，并保留原有结构：\n{latex}\n\n"
            "当前页的笔记内容如下：\n{markdown}\n\n"
            "如果上述 LaTeX 内容为空但笔记存在，请基于笔记生成新的、可直接编译的幻灯片内容。并且注意如有需要，记得用多个frame以防止单个页面的内容溢出\n"
            "严格遵守以下规则：\n"
            "1. 只使用当前模板已经加载的宏包({allowed_packages})和命令({custom_macros})，禁止新增宏包、字体或 \\usepackage/\\RequirePackage 指令。\n"
            "2. 不要输出 \\documentclass、\\begin{{document}}、\\end{{document}} 等全局结构，不要出现```latex，```等无关标记，只返回纯LaTeX代码。\n"
            "3. 不允许使用需要额外宏包才能编译的命令，也不要新增 \\newcommand/\\renewcommand/\\DeclareMathOperator 等定义。\n"
            "4. 输出内容的语言应该与我的原有内容一致，除非通过 % 特别要求。主要是 en 和 cn 两种。\n"
        ),
    },
}

AI_BIB_PROMPT = {
    "system": (
        "你是一名资深研究助理。"
        "接收任何网页链接或 DOI，输出一个 JSON 对象，总结该资源的关键信息。"
        "JSON 字段必须包含 label(50字以内记忆名), note(1-2句核心要点),"
        " id(推荐的引用键，仅含字母数字或-), link(首选规范化URL),"
        " metadata(对象，包含作者数组authors、年份year、来源venue、doi、type等可用信息)。"
        " 若是学术论文请返回 metadata.doi、metadata.authors(最多5位作者全名)、metadata.year、metadata.venue。"
        " 如能生成 BibTeX，可放在 bibtex 字段。"
        " 严格返回单个 JSON 对象，不要额外解释。"
    ),
    "user": (
        "请分析以下引用或网页，生成记忆名与重点摘要。"
        " 如果这是 DOI 论文，请尽可能补充论文的详细信息。\n"
        "输入: {ref}"
    ),
}

LEARNING_ASSISTANT_DEFAULT_PROMPTS = [
    {
        "id": "sentence_en",
        "name": "句子英语学习",
        "description": "翻译并润色句子，同时补充语法与文化背景知识。",
        "system": (
            "You are an experienced bilingual English-Chinese tutor. "
            "Explain grammar, nuance, and background in Chinese where appropriate, "
            "but keep important terminology bilingual. Provide clear, structured output in Markdown, "
            "and include LaTeX math when useful."
        ),
        "template": (
            "学习目标：针对以下句子进行英语学习，需包含翻译、语法结构解析、表达优化建议、相关文化或专业知识补充。\n"
            "主句内容：\n{content}\n\n"
            "可参考的上下文：\n{context}\n\n"
            "请输出以下部分：\n"
            "1. **翻译**：给出地道的中英文互译。\n"
            "2. **语法与结构解析**：逐句拆解，指出核心语法点和常见错误。\n"
            "3. **表达优化**：提供多种更自然或更正式的替换表达。\n"
            "4. **知识扩展**：补充与句子相关的背景知识、使用场景或学术信息。\n"
            "5. **练习建议**：给出巩固学习的练习或记忆方法。\n"
        ),
    },
    {
        "id": "word_en",
        "name": "单词英语学习",
        "description": "学习单词，包含词源、近反义词、例句与常识补充。",
        "system": (
            "You are an etymology-focused English vocabulary coach. "
            "Explain words with roots, affixes, synonyms, antonyms, usage notes, and memorable examples. "
            "Return Markdown with sections and bullet lists when helpful."
        ),
        "template": (
            "目标：全面学习以下词汇或短语。\n"
            "待学习词汇：\n{content}\n\n"
            "上下文（可选）：\n{context}\n\n"
            "请输出：\n"
            "1. **基本含义**（中英文）。\n"
            "2. **词根词缀与来源**，若无则说明。\n"
            "3. **词性与常见搭配**，至少给出 3 个例句，并附简短中文解释。\n"
            "4. **近义词 / 反义词对比**，指出差别和适用场景。\n"
            "5. **拓展知识**：与该词相关的文化、学科、专业常识或记忆技巧。\n"
        ),
    },
    {
        "id": "concept_new",
        "name": "新的知识概念",
        "description": "理解第一次遇到的概念，进行系统化拆解。",
        "system": (
            "You are a subject-matter expert and teacher. "
            "Break down new concepts for a curious learner with structured explanations, analogies, and practice suggestions."
        ),
        "template": (
            "请帮助学习者理解以下全新概念：\n{content}\n\n"
            "上下文信息：\n{context}\n\n"
            "请输出：\n"
            "1. **概念定义**：给出通俗版与专业版定义。\n"
            "2. **核心组成/关键要素**：用分点或流程说明。\n"
            "3. **类比与图示思路**：给出帮助记忆的类比或图像化描述。\n"
            "4. **典型应用场景**：列举至少两个实际案例或问题。\n"
            "5. **延伸阅读与练习建议**：推荐进一步学习路径。\n"
        ),
    },
    {
        "id": "code_explain",
        "name": "代码学习解析",
        "description": "解析代码逻辑，拓展相关知识与实践建议。",
        "system": (
            "You are a pragmatic software mentor. "
            "Explain code line-by-line, summarize algorithms, discuss complexity, best practices, and potential pitfalls."
        ),
        "template": (
            "需要解析的代码或伪代码片段如下：\n{content}\n\n"
            "额外上下文（若有）：\n{context}\n\n"
            "请输出：\n"
            "1. **功能概述**：说明代码整体意图和输入输出。\n"
            "2. **详细解析**：按逻辑块或行解释关键语句、数据结构、算法思想。\n"
            "3. **复杂度与性能**：分析时间/空间复杂度，指出瓶颈。\n"
            "4. **相关知识拓展**：关联框架、语言特性、常见替代写法或高级用法。\n"
            "5. **实践建议**：给出测试、调试、优化或安全方面的注意事项。\n"
        ),
    },
    {
        "id": "code_optimize",
        "name": "代码优化实战",
        "description": "在保持语义一致的前提下提出性能、结构与安全优化建议。",
        "system": (
            "You are a senior software architect and performance engineer. "
            "Focus on practical refactoring suggestions, measurable improvements, and potential risks."
        ),
        "template": (
            "请在不改变功能的情况下优化下面的代码或伪代码：\n{content}\n\n"
            "可参考的上下文（需求、约束、技术栈等）：\n{context}\n\n"
            "请输出：\n"
            "1. **问题扫描**：指出原实现中的性能、可维护性、安全或可读性问题。\n"
            "2. **优化方案**：提供改进后的代码或伪代码片段，必要时分步骤解释。\n"
            "3. **效果评估**：说明预期的性能/复杂度变化，或其他可量化收益。\n"
            "4. **回归与风险**：列出需要注意的兼容性、测试要点与潜在副作用。\n"
            "5. **进一步提升**：给出可选的工程化建议，如监控、自动化、工具链优化等。\n"
        ),
    },
    {
        "id": "markdown_math_polish",
        "name": "Markdown 笔记优化（含公式）",
        "description": "润色含数学公式的 Markdown 笔记，强调结构与渲染质量。",
        "system": (
            "You are a technical writing coach specializing in scientific Markdown. "
            "Preserve mathematical meaning, improve structure, and ensure formulas render well in common Markdown engines."
        ),
        "template": (
            "请优化以下含数学或技术内容的 Markdown 笔记：\n{content}\n\n"
            "补充上下文（可为空）：\n{context}\n\n"
            "请完成：\n"
            "1. **结构梳理**：调整标题层级、列表、段落顺序，使逻辑清晰。\n"
            "2. **公式与符号**：统一使用 `$...$` 或 `$$...$$`，排查未闭合/格式错误的表达式，并适当添加注释。\n"
            "3. **表达优化**：润色语言，使表述准确、紧凑，必要时补充定义或说明。\n"
            "4. **图表与引用建议**：提示可能需要的图示、参考文献、外部链接或进一步阅读。\n"
            "5. **检查清单**：列出渲染、编译或发布前应确认的要点。\n"
        ),
    },
    {
        "id": "ledger_insight",
        "name": "记账洞察助手",
        "description": "分析记账 Markdown，输出现金流洞察、风险提醒与行动建议。",
        "system": (
            "You are a trusted personal finance copilot. "
            "Summarize cash flow, spot anomalies, surface risks, and recommend actionable optimizations "
            "while keeping tone supportive and data-driven."
        ),
        "template": (
            "以下是我记录的记账 Markdown 内容，包含表格、列表或备注：\n{content}\n\n"
            "补充背景（预算目标、特殊事件等，可为空）：\n{context}\n\n"
            "请以个人财务助理的身份完成：\n"
            "1. **数据概览**：汇总总收入、总支出与净现金流，若数据缺失请说明假设。\n"
            "2. **类别洞察**：按类别/账户列出 2-3 个金额占比最高或变化异常的项目，解释原因。\n"
            "3. **风险与提醒**：指出潜在的现金流压力、重复订阅、过度消费或账务记录缺口。\n"
            "4. **优化建议**：给出具体的预算调整、消费替代、储蓄或投资建议，并说明预期影响。\n"
            "5. **下一步行动**：以待办清单形式输出 2-3 条可执行任务（含负责账户或时间节点）。\n"
        ),
    },
    {
        "id": "beamer_polish",
        "name": "LaTeX Beamer 优化",
        "description": "优化 Beamer 幻灯片代码与排版，确保兼容现有模板。",
        "system": (
            "You are a LaTeX Beamer specialist. "
            "Respect existing template constraints, avoid introducing new packages, and focus on presentation clarity."
        ),
        "template": (
            "需要优化的 Beamer 幻灯片代码如下：\n{content}\n\n"
            "可参考的上下文（当前主题、受众、语言等）：\n{context}\n\n"
            "请提供：\n"
            "1. **主要问题**：指出排版、结构或风格上的不足。\n"
            "2. **优化后的代码**：在现有宏包限制下给出改进版，必要时拆分为多个 frame，并保持可直接编译。\n"
            "3. **视觉与叙事建议**：针对文字密度、重点突出、颜色或动画提出改进意见。\n"
            "4. **后续检查**：列出编译、演示或分享前需要确认的事项。\n"
        ),
    },
]

COMPONENT_LIBRARY = {
    "latex": [
        {
            "group": "结构",
            "items": [
                {"name": "章节（Section）", "code": "\\section{章节标题}"},
                {"name": "小节（Subsection）", "code": "\\subsection{小节标题}"},
                {"name": "幻灯片标题", "code": "\\frametitle{幻灯片标题}"},
                {"name": "幻灯片副标题", "code": "\\framesubtitle{幻灯片副标题}"},
                {
                    "name": "摘要（Abstract）",
                    "code": "\\begin{abstract}\n这里是摘要内容。\n\\end{abstract}",
                },
                {
                    "name": "目录（Table of Contents）",
                    "code": "\\tableofcontents",
                },
                {
                    "name": "过渡页",
                    "code": "\\begin{frame}[plain]\n  \\centering\\Huge 章节标题\n\\end{frame}",
                },
            ],
        },
        {
            "group": "排版",
            "items": [
                {
                    "name": "两栏排版",
                    "code": "\\begin{columns}\n  \\column{0.5\\textwidth}\n  左侧内容\n  \\column{0.5\\textwidth}\n  右侧内容\n\\end{columns}",
                },
                {
                    "name": "左右两列上下分块",
                    "code": "\\begin{columns}[T,onlytextwidth]\n  \\column{0.48\\textwidth}\n  % 左侧内容\n  这里是左侧一整块内容\n  \\column{0.48\\textwidth}\n  % 右侧上块\n  \\textbf{右上块标题}\n  右上块内容\\\\[1em]\n  % 右侧下块\n  \\textbf{右下块标题}\n  右下块内容\n\\end{columns}",
                },
                {
                    "name": "田字格（2x2分栏）",
                    "code": "\\begin{columns}\n  \\column{0.5\\textwidth}\n    \\begin{block}{左上}\n    内容1\n    \\end{block}\n    \\begin{block}{左下}\n    内容2\n    \\end{block}\n  \\column{0.5\\textwidth}\n    \\begin{block}{右上}\n    内容3\n    \\end{block}\n    \\begin{block}{右下}\n    内容4\n    \\end{block}\n\\end{columns}",
                },
                {
                    "name": "三列关键点",
                    "code": "\\begin{columns}[onlytextwidth]\n  \\column{0.32\\textwidth}\n  \\begin{block}{要点一}\n  内容 A\n  \\end{block}\n  \\column{0.32\\textwidth}\n  \\begin{block}{要点二}\n  内容 B\n  \\end{block}\n  \\column{0.32\\textwidth}\n  \\begin{block}{要点三}\n  内容 C\n  \\end{block}\n\\end{columns}",
                },
                {
                    "name": "引用块（Quote）",
                    "code": "\\begin{quote}\n引用内容。\n\\end{quote}",
                },
            ],
        },
        {
            "group": "组件",
            "items": [
                {
                    "name": "项目符号列表",
                    "code": "\\begin{itemize}\n  \\item 第一项\n  \\item 第二项\n\\end{itemize}",
                },
                {
                    "name": "编号列表",
                    "code": "\\begin{enumerate}\n  \\item 第一项\n  \\item 第二项\n\\end{enumerate}",
                },
                {
                    "name": "表格",
                    "code": "\\begin{tabular}{|c|c|c|}\n  \\hline\nA & B & C \\\\ \\hline\n1 & 2 & 3 \\\\ \\hline\n\\end{tabular}",
                },
                {
                    "name": "浮动表格（table）",
                    "code": "\\begin{table}[htbp]\n  \\centering\n  \\begin{tabular}{ccc}\n    A & B & C \\\\ \n    1 & 2 & 3 \\\\ \n  \\end{tabular}\n  \\caption{表格标题}\n  \\label{tab:label}\n\\end{table}",
                },
                {
                    "name": "代码块（verbatim）",
                    "code": "\\begin{verbatim}\n这里是代码内容\n\\end{verbatim}",
                },
                {
                    "name": "交叉引用",
                    "code": "见图\\ref{fig:label}，表\\ref{tab:label}，公式\\eqref{eq:label}",
                },
            ],
        },
        {
            "group": "数学/定理",
            "items": [
                {
                    "name": "公式（有编号）",
                    "code": "\\begin{equation}\n  E=mc^2\n  \\end{equation}",
                },
                {
                    "name": "公式（无编号）",
                    "code": "\\[ E^2 = p^2c^2 + m^2c^4 \\]",
                },
                {
                    "name": "定理（theorem）",
                    "code": "\\begin{theorem}\n  定理内容。\n  \\end{theorem}",
                },
                {
                    "name": "证明（proof）",
                    "code": "\\begin{proof}\n  证明过程。\n  \\end{proof}",
                },
                {
                    "name": "公式排列（align）",
                    "code": "\\begin{align}\n  f(x) &= x^2 + 1 \\ \\n  f'(x) &= 2x\\,.\n\\end{align}",
                },
            ],
        },
        {
            "group": "卡片",
            "items": [
                {
                    "name": "普通卡片（block）",
                    "code": "\\begin{block}{卡片标题}\n  这里是卡片内容，可用于强调信息。\n  \\end{block}",
                },
                {
                    "name": "警告卡片（alertblock）",
                    "code": "\\begin{alertblock}{警告/高亮}\n  这里是高亮警告内容。\n  \\end{alertblock}",
                },
                {
                    "name": "示例卡片（exampleblock）",
                    "code": "\\begin{exampleblock}{示例}\n  这里是示例内容。\n  \\end{exampleblock}",
                },
            ],
        },
        {
            "group": "图片",
            "items": [
                {
                    "name": "插入图片",
                    "code": "\\begin{center}\n  \\includegraphics[width=0.7\\textwidth]{example-image}\n\\end{center}",
                },
                {
                    "name": "浮动图片（figure）",
                    "code": "\\begin{figure}[htbp]\n  \\centering\n  \\includegraphics[width=0.6\\textwidth]{example-image}\n  \\caption{图片标题}\n  \\label{fig:label}\n\\end{figure}",
                },
                {
                    "name": "双图对比",
                    "code": "\\begin{figure}[htbp]\n  \\centering\n  \\begin{subfigure}{0.48\\textwidth}\n    \\includegraphics[width=\\linewidth]{example-image-a}\n    \\caption{左图}\n  \\end{subfigure}\n  \\hfill\n  \\begin{subfigure}{0.48\\textwidth}\n    \\includegraphics[width=\\linewidth]{example-image-b}\n    \\caption{右图}\n  \\end{subfigure}\n\\end{figure}",
                },
            ],
        },
    ],
    "markdown": [
        {
            "group": "模板",
            "items": [
                {
                    "name": "Blog Front Matter",
                    "code": "---\ncover: https://example.com/cover.jpg\ndate: \"2025-01-01\"\nstatus: draft\nsummary: |\n  在这里撰写文章摘要，支持多行描述。\ntags:\n  - 标签一\n  - 标签二\ntitle: \"文章标题\"\ncategories:\n  - 默认分类\nslug: my-blog-post\n---\n\n# 主标题\n\n正文从这里开始……\n",
                },
                {
                    "name": "日记模板",
                    "code": "---\ndate: \"2025-01-01\"\nmood: 😊\nweather: 晴\nkeywords:\n  - 生活\n  - 感悟\n---\n\n## 今日亮点\n- \n\n## 遇到的挑战\n- \n\n## 学到的事情\n- \n\n## 明日计划\n- \n",
                },
                {
                    "name": "记账模板",
                    "code": (
                        "---\n"
                        "date: \"2025-01-01\"\n"
                        "account_book: \"默认账本\"\n"
                        "currency: CNY\n"
                        "mood: 😊\n"
                        "focus: \"本周消费反思\"\n"
                        "tags:\n"
                        "  - 日常\n"
                        "  - 消费记录\n"
                        "---\n"
                        "\n"
                        "## 今日概览\n"
                        "- **总收入**：￥0.00\n"
                        "- **总支出**：￥0.00\n"
                        "- **净现金流**：`= 收入合计 - 支出合计`\n"
                        "- **预算偏差**：`= 今日实际 - 预算`\n"
                        "- **备注/情绪**：\n"
                        "\n"
                        "## 收支明细\n"
                        "| 时间 | 类别 | 子类 | 账户 | 描述 | 收入 | 支出 |\n"
                        "| ---- | ---- | ---- | ---- | ---- | ---- | ---- |\n"
                        "| 08:30 | 工作 | 工资 | 工资账户 | 1 月薪资 | 500.00 | 0.00 |\n"
                        "| 12:10 | 生活 | 午餐 | 数字钱包 | 商务午餐 | 0.00 | 38.00 |\n"
                        "\n"
                        "## 固定支出 / 订阅检查\n"
                        "- [ ] 项目 / 金额 / 到期时间\n"
                        "\n"
                        "## 预算与目标\n"
                        "- 本周目标：\n"
                        "- 进展点评：\n"
                        "\n"
                        "## 财务反思\n"
                        "- 今日洞察：\n"
                        "- 明日行动：\n"
                    ),
                },
                {
                    "name": "会议笔记模板",
                    "code": (
                        "---\n"
                        "meeting: 项目例会\n"
                        "type: 周会\n"
                        "date: \"2025-01-01\"\n"
                        "time: \"10:00-11:00\"\n"
                        "location: 远程会议室\n"
                        "facilitator: 张三\n"
                        "attendees:\n"
                        "  - 张三 / PM\n"
                        "  - 李四 / Tech Lead\n"
                        "objective: |\n"
                        "  用一段话明确会议目标与衡量标准。\n"
                        "context: \"背景 / 版本 / 关联项目\"\n"
                        "---\n"
                        "\n"
                        "## 议程概览\n"
                        "| 时间 | 议题 | 引导人 | 预期输出 |\n"
                        "| ---- | ---- | ------ | -------- |\n"
                        "| 10:00 | 例行进度同步 | 张三 | 完成状态更新 |\n"
                        "| 10:25 | 风险评估 | 李四 | 更新风险列表 |\n"
                        "\n"
                        "## 进度与阻塞\n"
                        "- 模块 A：当前状态 / 里程碑 / 阻塞点\n"
                        "- 模块 B：\n"
                        "\n"
                        "## 讨论与决策记录\n"
                        "| 议题 | 核心信息 | 决策/结论 | 责任人 | 截止时间 |\n"
                        "| ---- | -------- | ---------- | ------ | -------- |\n"
                        "| 示例 | 要点 | 决策 | 负责人 | YYYY-MM-DD |\n"
                        "\n"
                        "## Action Items\n"
                        "- [ ] 任务名称 | Owner | Due | 所需支持\n"
                        "\n"
                        "## 风险 & 依赖\n"
                        "- 风险描述 / 影响范围 / 缓解动作\n"
                        "\n"
                        "## 待向上反馈 / 外部同步\n"
                        "- \n"
                    ),
                },
                {
                    "name": "课堂/读书笔记模板",
                    "code": (
                        "---\n"
                        "topic: 课程/书籍名称\n"
                        "date: \"2025-01-01\"\n"
                        "source: \"来源或讲者\"\n"
                        "format: 线上课程\n"
                        "difficulty: 中等\n"
                        "tags:\n"
                        "  - 知识管理\n"
                        "  - 专业技能\n"
                        "learning_goal: \"我希望解决的具体问题\"\n"
                        "---\n"
                        "\n"
                        "## 章节脉络\n"
                        "| 章节 | 核心命题 | 证据/案例 |\n"
                        "| ---- | -------- | --------- |\n"
                        "| 第 1 章 | | |\n"
                        "\n"
                        "## 核心概念拆解\n"
                        "- 概念：定义 / 关键公式 / 适用场景\n"
                        "- 概念：\n"
                        "\n"
                        "## 重点摘录\n"
                        "> 原文节选（引用 + 页码或时间戳）\n"
                        ">\n"
                        "> 自己的理解：\n"
                        "\n"
                        "## 思考与疑问\n"
                        "- 现有认知冲突：\n"
                        "- 待进一步求证的问题：\n"
                        "\n"
                        "## 应用与行动\n"
                        "- 场景假设：\n"
                        "- 行动实验：\n"
                        "- 复盘指标：\n"
                    ),
                },
                {
                    "name": "日程规划安排模板",
                    "code": (
                        "---\n"
                        "date: \"2025-01-01\"\n"
                        "week: \"Week 01\"\n"
                        "focus_mission: \"当天最高优先级任务\"\n"
                        "energy_curve:\n"
                        "  morning: 高\n"
                        "  afternoon: 中\n"
                        "  evening: 低\n"
                        "habits:\n"
                        "  - 运动\n"
                        "  - 阅读\n"
                        "---\n"
                        "\n"
                        "## 今日三大目标\n"
                        "1. \n"
                        "2. \n"
                        "3. \n"
                        "\n"
                        "## 时间区块\n"
                        "| 时间 | 事项 | 预期成果 | 提醒 |\n"
                        "| ---- | ---- | -------- | ---- |\n"
                        "| 08:30-10:00 | 深度工作 | 模块交付 | 关闭通知 |\n"
                        "\n"
                        "## 优先级清单\n"
                        "- P0：\n"
                        "- P1：\n"
                        "- P2：\n"
                        "\n"
                        "## 沟通/会议\n"
                        "| 时间 | 主题 | 参与人 | 需要准备 |\n"
                        "| ---- | ---- | ------ | -------- |\n"
                        "\n"
                        "## 生活/健康\n"
                        "- 运动：\n"
                        "- 饮水/餐食：\n"
                        "- 休息提醒：\n"
                        "\n"
                        "## 日终复盘\n"
                        "- 完成度：\n"
                        "- 情绪/能量观察：\n"
                        "- 明日微调：\n"
                    ),
                },
                {
                    "name": "活动组织模板",
                    "code": (
                        "---\n"
                        "event_name: 春季客户见面会\n"
                        "theme: \"以客户成功为中心\"\n"
                        "date_range: \"2025-03-10 ~ 2025-03-12\"\n"
                        "location: 上海会议中心\n"
                        "owner: 王五\n"
                        "expected_attendees: 120\n"
                        "budget: 200000\n"
                        "partners:\n"
                        "  - 供应商A\n"
                        "  - 媒体B\n"
                        "---\n"
                        "\n"
                        "## 活动目标与受众画像\n"
                        "- 目标：品牌曝光 / 转化 / 社群维护\n"
                        "- 核心受众：\n"
                        "\n"
                        "## 关键里程碑\n"
                        "| 截止时间 | 事项 | 负责人 | 状态 |\n"
                        "| -------- | ---- | ------ | ---- |\n"
                        "| 02-15 | 场地确认 | 王五 | 进行中 |\n"
                        "\n"
                        "## 资源与分工\n"
                        "- 策划：\n"
                        "- 运营：\n"
                        "- 物料：\n"
                        "- 技术支持：\n"
                        "\n"
                        "## 宣传/报名计划\n"
                        "- 渠道：邮件 / 社媒 / 社群\n"
                        "- 关键信息：\n"
                        "- 指标：报名人数 / 转化率\n"
                        "\n"
                        "## 活动当日日程\n"
                        "| 时间 | 环节 | 负责人 | 备注 |\n"
                        "| ---- | ---- | ------ | ---- |\n"
                        "| 09:00 | 签到 | 前台组 | 准备礼品 |\n"
                        "\n"
                        "## 风险与应急预案\n"
                        "- 风险：\n"
                        "- 应急措施：\n"
                        "\n"
                        "## 复盘要点\n"
                        "- 成果指标：到场人数 / NPS / 成交\n"
                        "- 学习与改进：\n"
                    ),
                },
            ],
        },
        {
            "group": "基础",
            "items": [
                {"name": "二级标题", "code": "## 小节标题\n\n这里是内容简介。"},
                {
                    "name": "任务清单",
                    "code": "- [ ] 待办事项一\n- [x] 已完成事项",
                },
                {
                    "name": "引用块",
                    "code": "> 引用内容，可用于强调某句文字。",
                },
                {
                    "name": "分割线",
                    "code": "---\n",
                },
            ],
        },
        {
            "group": "布局",
            "items": [
                {
                    "name": "两列对比",
                    "code": "<table>\n  <tr>\n    <th>优势</th>\n    <th>劣势</th>\n  </tr>\n  <tr>\n    <td>内容 A</td>\n    <td>内容 B</td>\n  </tr>\n</table>\n",
                },
                {
                    "name": "信息卡片",
                    "code": ":::info\n标题\n\n说明内容。\n:::\n",
                },
            ],
        },
        {
            "group": "列表与表格",
            "items": [
                {
                    "name": "嵌套列表",
                    "code": "- 一级要点\n  - 二级要点\n    - 三级要点",
                },
                {
                    "name": "简单表格",
                    "code": "| 项目 | 指标 | 说明 |\n| ---- | ---- | ---- |\n| A    | 95   | 描述A |\n| B    | 88   | 描述B |",
                },
            ],
        },
        {
            "group": "代码与提示",
            "items": [
                {
                    "name": "代码块",
                    "code": "```python\nprint('Hello World')\n```",
                },
                {
                    "name": "提示块",
                    "code": ":::tip\n关键提示写在这里。\n:::\n",
                },
                {
                    "name": "警告块",
                    "code": ":::warning\n需要注意的内容。\n:::\n",
                },
            ],
        },
        {
            "group": "媒体",
            "items": [
                {
                    "name": "插入图片",
                    "code": "![图片说明](path/to/image.png)",
                },
                {
                    "name": "插入视频",
                    "code": "<video controls width=\"640\">\n  <source src=\"path/to/video.mp4\" type=\"video/mp4\">\n  您的浏览器不支持 HTML5 视频。\n</video>\n",
                },
                {
                    "name": "插入音频",
                    "code": "<audio controls>\n  <source src=\"path/to/audio.mp3\" type=\"audio/mpeg\">\n  您的浏览器不支持音频播放。\n</audio>\n",
                },
                {
                    "name": "嵌入链接",
                    "code": "[相关链接](https://example.com)",
                },
            ],
        },
    ],
}

UI_THEME = {
    "color_mode": os.environ.get("BENORT_COLOR_MODE", "light"),  # light | dark
    "navbar_buttons": {
        "preset": os.environ.get("BENORT_NAVBAR_PRESET", "modern"),
        "style": os.environ.get("BENORT_NAVBAR_STYLE", "uniform"),  # uniform | palette
        "variant": os.environ.get("BENORT_NAVBAR_VARIANT", "outline"),  # outline | solid
        "color": os.environ.get("BENORT_NAVBAR_COLOR", "primary"),
        "palette": [
            c.strip() for c in (os.environ.get("BENORT_NAVBAR_PALETTE") or "primary,success,warning,danger,info")
            .split(',') if c.strip()
        ] or ["primary"],
    },
}


def template_library_root(app: object | None = None) -> str:
    """确定可复用 LaTeX 模板所在目录。"""

    if app is not None:
        # 在应用上下文内优先读取配置值
        root = getattr(app, "config", {}).get("TEMPLATE_LIBRARY")  # type: ignore[arg-type]
        if root:
            return root
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "temps"))


def init_app_config(app) -> None:
    """根据应用根目录初始化项目与模板文件夹。"""

    projects_root = os.path.join(app.root_path, "projects")
    app.config.setdefault("PROJECTS_ROOT", projects_root)

    # 预先加载 OSS 配置，允许通过环境变量覆盖
    app.config.setdefault("ALIYUN_OSS_ENDPOINT", os.environ.get("ALIYUN_OSS_ENDPOINT"))
    app.config.setdefault("ALIYUN_OSS_ACCESS_KEY_ID", os.environ.get("ALIYUN_OSS_ACCESS_KEY_ID"))
    app.config.setdefault("ALIYUN_OSS_ACCESS_KEY_SECRET", os.environ.get("ALIYUN_OSS_ACCESS_KEY_SECRET"))
    app.config.setdefault("ALIYUN_OSS_BUCKET", os.environ.get("ALIYUN_OSS_BUCKET"))
    app.config.setdefault("ALIYUN_OSS_PREFIX", os.environ.get("ALIYUN_OSS_PREFIX"))
    app.config.setdefault("ALIYUN_OSS_PUBLIC_BASE_URL", os.environ.get("ALIYUN_OSS_PUBLIC_BASE_URL"))

    template_root = template_library_root(app)
    app.config.setdefault("TEMPLATE_LIBRARY", template_root)
    os.makedirs(template_root, exist_ok=True)


__all__ = [
    "DEFAULT_PROJECT_NAME",
    "DEFAULT_TEMPLATE_FILENAME",
    "DEFAULT_MARKDOWN_TEMPLATE_FILENAME",
    "FALLBACK_TEMPLATE",
    "FALLBACK_MARKDOWN_TEMPLATE",
    "OPENAI_CHAT_COMPLETIONS_MODEL",
    "OPENAI_API_BASE_URL",
    "OPENAI_CHAT_PATH",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_EMBEDDING_PATH",
    "DEFAULT_TTS_MODEL",
    "DEFAULT_TTS_PATH",
    "CHATANYWHERE_EMBEDDING_MODEL",
    "CHATANYWHERE_TTS_MODEL",
    "CHATANYWHERE_EMBEDDING_PATH",
    "CHATANYWHERE_TTS_PATH",
    "CHATANYWHERE_API_BASE_URL",
    "CHATANYWHERE_CHAT_PATH",
    "CHATANYWHERE_DEFAULT_MODEL",
    "LLM_PROVIDERS",
    "DEFAULT_LLM_PROVIDER",
    "OPENAI_TTS_MODEL",
    "OPENAI_TTS_VOICE",
    "OPENAI_TTS_RESPONSE_FORMAT",
    "OPENAI_TTS_SPEED",
    "AI_PROMPTS",
    "AI_BIB_PROMPT",
    "LEARNING_ASSISTANT_DEFAULT_PROMPTS",
    "COMPONENT_LIBRARY",
    "UI_THEME",
    "init_app_config",
    "template_library_root",
]
