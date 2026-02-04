# 解析流程示例（含导言区/作者/Caption）

## 原始 TeX 示例

```tex
\documentclass{article}
\title{A Simple Paper}
\author{Alice \\ Bob}
\begin{document}
\maketitle

\begin{abstract}
Abstract with inline math $a+b$ and a cite \cite{smith2020}.
\end{abstract}

\section{Intro \label{sec:intro}}
We refer to Eq.~\eqref{eq:one} and Figure~\ref{fig:one}. See \url{https://example.com} and \href{https://example.com}{link}.
Here is a footnote\footnote{Footnote text with a ref \ref{sec:intro}.}

\begin{figure}
\centering
\includegraphics{fig1}
\caption{An example figure caption.}
\label{fig:one}
\end{figure}

\begin{equation}
E = mc^2
\label{eq:one}
\end{equation}

Inline math $x+y$ continues here.
\end{document}
```

## 步骤 0：拆分导言区/正文
- 函数：`_split_preamble_body`
- 方法：正则匹配 `\begin{document}`

### 导言区（preamble）
```
\documentclass{article}
\title{A Simple Paper}
\author{Alice \\ Bob}
\begin{document}
```

### 正文（body）
```
\maketitle

\begin{abstract}
Abstract with inline math $a+b$ and a cite \cite{smith2020}.
\end{abstract}

\section{Intro \label{sec:intro}}
We refer to Eq.~\eqref{eq:one} and Figure~\ref{fig:one}. See \url{https://example.com} and \href{https://example.com}{link}.
Here is a footnote\footnote{Footnote text with a ref \ref{sec:intro}.}

\begin{figure}
\centering
\includegraphics{fig1}
\caption{An example figure caption.}
\label{fig:one}
\end{figure}

\begin{equation}
E = mc^2
\label{eq:one}
\end{equation}

Inline math $x+y$ continues here.
```

## 步骤 1：导言区标题抽取
- 函数：`_extract_title_from_preamble`
- 方法：正则 + 大括号计数（brace counting）

```
\documentclass{article}
\title{{CHUNK_T}}
\author{Alice \\ Bob}
\begin{document}
```

CHUNK_T = `A Simple Paper`

## 步骤 2：正文处理顺序（_process_body）
调用顺序固定为：
1) `_protect_author_block`
2) `_extract_captions`
3) `_protect_math_environments`
4) `_protect_inline_math`
5) `_protect_commands`
6) `_extract_translatable_content`

下面逐步展示变化。

## 步骤 2.1：保护作者块
- 函数：`_protect_author_block`
- 方法：正则 + 大括号计数
- 本例正文中无 `\author{}`，所以不变

## 步骤 2.2：抽取 caption
- 函数：`_extract_captions`
- 方法：正则 + 大括号计数

```
\maketitle

\begin{abstract}
Abstract with inline math $a+b$ and a cite \cite{smith2020}.
\end{abstract}

\section{Intro \label{sec:intro}}
We refer to Eq.~\eqref{eq:one} and Figure~\ref{fig:one}. See \url{https://example.com} and \href{https://example.com}{link}.
Here is a footnote\footnote{Footnote text with a ref \ref{sec:intro}.}

\begin{figure}
\centering
\includegraphics{fig1}
\caption{{CHUNK_CAP}}
\label{fig:one}
\end{figure}

\begin{equation}
E = mc^2
\label{eq:one}
\end{equation}

Inline math $x+y$ continues here.
```

CHUNK_CAP = `An example figure caption.`

## 步骤 2.3：保护数学环境（environment）
- 函数：`_protect_math_environments` / `_protect_single_environment`
- 方法：正则匹配 `\begin{env}` + 环境嵌套计数（env_count）

```
\maketitle

\begin{abstract}
Abstract with inline math $a+b$ and a cite \cite{smith2020}.
\end{abstract}

\section{Intro \label{sec:intro}}
We refer to Eq.~\eqref{eq:one} and Figure~\ref{fig:one}. See \url{https://example.com} and \href{https://example.com}{link}.
Here is a footnote\footnote{Footnote text with a ref \ref{sec:intro}.}

\begin{figure}
\centering
\includegraphics{fig1}
\caption{{CHUNK_CAP}}
\label{fig:one}
\end{figure}

[[MATHENV_1]]

Inline math $x+y$ continues here.
```

## 步骤 2.4：保护行内数学（inline_math）
- 函数：`_protect_inline_math` / `_protect_display_math_delimiters`
- 方法：手写扫描（字符级遍历），识别 `$...$` / `$$...$$` / `\(...\)` / `\[...\]`

```
\maketitle

\begin{abstract}
Abstract with inline math [[MATH_2]] and a cite \cite{smith2020}.
\end{abstract}

\section{Intro \label{sec:intro}}
We refer to Eq.~\eqref{eq:one} and Figure~\ref{fig:one}. See \url{https://example.com} and \href{https://example.com}{link}.
Here is a footnote\footnote{Footnote text with a ref \ref{sec:intro}.}

\begin{figure}
\centering
\includegraphics{fig1}
\caption{{CHUNK_CAP}}
\label{fig:one}
\end{figure}

[[MATHENV_1]]

Inline math [[MATH_3]] continues here.
```

## 步骤 2.5：保护命令（command）
- 函数：`_protect_commands` / `_protect_nested_command` / `_protect_includegraphics`
- 方法：正则匹配命令头 + 大括号计数（`cite/ref/eqref/label/url/footnote/href`），`includegraphics` 单独正则 + 计数

```
\maketitle

\begin{abstract}
Abstract with inline math [[MATH_2]] and a cite [[CITE_4]].
\end{abstract}

\section{Intro [[LABEL_8]]}
We refer to Eq.~[[REF_7]] and Figure~[[REF_5]]. See [[URL_10]] and [[HREF_12]].
Here is a footnote[[FOOTNOTE_11]]

\begin{figure}
\centering
[[GRAPHICS_13]]
\caption{{CHUNK_CAP}}
[[LABEL_9]]
\end{figure}

[[MATHENV_1]]

Inline math [[MATH_3]] continues here.
```

说明：命令替换的编号按“命令类型遍历顺序”递增（先 cite，再 ref，再 eqref，再 label...），不是按文本出现顺序。

## 步骤 2.6：抽取可翻译内容（chunk）
- 函数：`_extract_translatable_content`
- 方法：
  - `SECTION_COMMANDS`：`_extract_section_command`（正则 + 大括号计数）
  - `TRANSLATABLE_ENVIRONMENTS`：`_extract_translatable_environment`（正则 + 环境嵌套计数）
  - 段落切分：`_chunk_paragraphs` + `_maybe_chunk_paragraph`（行级扫描 + 长度阈值）

```
\maketitle

\begin{abstract}
{{CHUNK_ABS}}
\end{abstract}

\section{{CHUNK_SEC}}
{{CHUNK_P1}}

\begin{figure}
\centering
[[GRAPHICS_13]]
\caption{{CHUNK_CAP}}
[[LABEL_9]]
\end{figure}

[[MATHENV_1]]

{{CHUNK_P2}}
```

其中：
- CHUNK_ABS = `Abstract with inline math [[MATH_2]] and a cite [[CITE_4]].`
- CHUNK_SEC = `Intro [[LABEL_8]]`
- CHUNK_P1 = `We refer to Eq.~[[REF_7]] and Figure~[[REF_5]]. See [[URL_10]] and [[HREF_12]].\nHere is a footnote[[FOOTNOTE_11]]`
- CHUNK_P2 = `Inline math [[MATH_3]] continues here.`

## 步骤 3：重建（reconstruct）
- 函数：`Chunk.reconstruct` / `LaTeXDocument.reconstruct`
- 方法：字符串替换（replace），先替换 `{{CHUNK_uuid}}`，再恢复 `[[...]]`

结果：`{{CHUNK_*}}` 被翻译文本替换，`[[MATHENV_*]]/[[MATH_*]]/[[CITE_*]]/...` 被还原为原 LaTeX 命令或环境。
