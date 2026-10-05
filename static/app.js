/* Enterprise Document Intelligence Assistant —— 前端逻辑 */
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  const dropzone = $("#dropzone");
  const fileInput = $("#file-input");
  const uploadStatus = $("#upload-status");
  const docList = $("#doc-list");
  const chatScroll = $("#chat-scroll");
  const queryInput = $("#query-input");
  const sendBtn = $("#send-btn");

  const FORMAT_TAGS = { PDF: "pdf", Word: "word", Markdown: "md", 文本: "txt", 文档: "txt" };

  // ---------- 状态 ----------
  const PROVIDER_NAMES = {
    offline: "离线演示", openai: "OpenAI", qwen: "通义千问",
    zhipu: "智谱AI", deepseek: "DeepSeek", moonshot: "月之暗面", siliconflow: "硅基流动",
  };
  async function loadStatus() {
    try {
      const res = await fetch("/api/health");
      const data = await res.json();
      $("#badge-docs").textContent = `文档 ${data.stats.doc_count}`;
      $("#badge-chunks").textContent = `片段 ${data.stats.chunk_count}`;
      const pname = PROVIDER_NAMES[data.model_provider] || data.model_provider || "未知";
      const llm = data.llm_engine === "api" ? `${pname} · ${data.llm_model}` : "离线引用模板";
      $("#badge-mode").textContent = `模型：${llm} · 向量：${data.embedding_mode === "api" ? "语义" : "离线"}`;
      $("#badge-mode").title = `模型 ${data.llm_model} | Embedding ${data.embedding_model}`;
    } catch (e) {
      $("#badge-mode").textContent = "引擎：服务未连接";
    }
  }

  async function loadDocs() {
    try {
      const res = await fetch("/api/documents");
      const data = await res.json();
      renderDocs(data.documents || []);
    } catch (e) {
      renderDocs([]);
    }
  }

  function renderDocs(docs) {
    docList.innerHTML = "";
    if (!docs.length) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = "暂无文档，请先上传";
      docList.appendChild(li);
      return;
    }
    docs.forEach((doc) => {
      const li = document.createElement("li");
      li.className = "doc-item";

      const fmt = doc.format || "文档";
      const tag = FORMAT_TAGS[fmt] || "txt";
      const icon = document.createElement("div");
      icon.className = `doc-icon ${tag}`;
      icon.textContent = fmt.slice(0, 2).toUpperCase();

      const info = document.createElement("div");
      info.className = "doc-info";
      const name = document.createElement("div");
      name.className = "doc-name";
      name.textContent = doc.name;
      const meta = document.createElement("div");
      meta.className = "doc-meta";
      meta.textContent = `${doc.chunk_count} 个片段 · ${doc.created_at || ""}`.trim();
      info.append(name, meta);

      const del = document.createElement("button");
      del.className = "doc-del";
      del.title = "从知识库删除";
      del.textContent = "✕";
      del.addEventListener("click", () => removeDoc(doc.id, doc.name));

      li.append(icon, info, del);
      docList.appendChild(li);
    });
  }

  async function removeDoc(id, name) {
    if (!confirm(`确定从知识库删除《${name}》吗？`)) return;
    const res = await fetch(`/api/documents/${id}`, { method: "DELETE" });
    if (res.ok) {
      toast(`已删除《${name}》`);
      loadDocs();
      loadStatus();
    }
  }

  // ---------- 上传 ----------
  function setStatus(html, cls) {
    uploadStatus.innerHTML = html;
    uploadStatus.className = `upload-status ${cls || ""}`;
  }

  async function uploadFiles(files) {
    for (const file of Array.from(files)) {
      setStatus(`正在解析并入库 <b>${escapeHtml(file.name)}</b>…`, "pending");
      const fd = new FormData();
      fd.append("file", file);
      try {
        const res = await fetch("/api/documents", { method: "POST", body: fd });
        const data = await res.json();
        if (!res.ok) {
          setStatus(`✕ ${escapeHtml(data.detail || "上传失败")}`, "err");
        } else {
          setStatus(`✓ ${escapeHtml(data.message)}（${data.chunks} 个片段）`, "ok");
        }
      } catch (e) {
        setStatus(`✕ 网络错误：${escapeHtml(e.message)}`, "err");
      }
    }
    loadDocs();
    loadStatus();
  }

  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    uploadFiles(e.dataTransfer.files);
  });
  fileInput.addEventListener("change", () => {
    uploadFiles(fileInput.files);
    fileInput.value = "";
  });

  // ---------- 问答 ----------
  async function ask() {
    const query = queryInput.value.trim();
    if (!query || sendBtn.disabled) return;

    queryInput.value = "";
    appendMsg("user", query);
    appendTyping();

    sendBtn.disabled = true;
    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const data = await res.json();
      if (!res.ok) {
        replaceTyping(data.answer || "服务异常，请稍后重试", true);
      } else {
        replaceTyping(data.answer, !data.grounded, data.citations || [], data.retrieved_count || 0);
      }
    } catch (e) {
      replaceTyping("网络错误，请检查服务是否启动。", true);
    } finally {
      sendBtn.disabled = false;
    }
  }

  sendBtn.addEventListener("click", ask);
  queryInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      ask();
    }
  });

  // ---------- 渲染 ----------
  function appendMsg(role, text) {
    const div = document.createElement("div");
    div.className = `msg ${role}`;
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;
    div.appendChild(bubble);
    chatScroll.appendChild(div);
    chatScroll.scrollTop = chatScroll.scrollHeight;
    return div;
  }

  function appendTyping() {
    const div = document.createElement("div");
    div.className = "msg assistant";
    const bubble = document.createElement("div");
    bubble.className = "bubble typing";
    bubble.textContent = "正在检索知识库并生成回答…";
    div.appendChild(bubble);
    chatScroll.appendChild(div);
    chatScroll.scrollTop = chatScroll.scrollHeight;
    return div;
  }

  function replaceTyping(answer, noGround, citations, retrievedCount) {
    const typingMsg = chatScroll.querySelector(".msg.assistant:last-child");
    const div = typingMsg || document.createElement("div");
    div.className = "msg assistant" + (noGround ? " no-ground" : "");
    const bubble = document.createElement("div");
    bubble.className = "bubble";

    const p = document.createElement("p");
    p.textContent = answer;
    bubble.appendChild(p);

    if (citations && citations.length) {
      const wrap = document.createElement("div");
      wrap.className = "citations";
      const title = document.createElement("div");
      title.className = "cite-title";
      title.textContent = `引用来源（检索到 ${retrievedCount} 个相关片段，已过滤低相关）`;
      wrap.appendChild(title);
      citations.forEach((c, i) => wrap.appendChild(buildCiteCard(c, i + 1)));
      bubble.appendChild(wrap);
    } else if (noGround) {
      const note = document.createElement("p");
      note.className = "no-ground-note";
      note.textContent = "未引用任何文档：未找到足够相关内容，已拒绝作答（防幻觉）";
      bubble.appendChild(note);
    }

    div.innerHTML = "";
    div.appendChild(bubble);
    if (!typingMsg) chatScroll.appendChild(div);
    chatScroll.scrollTop = chatScroll.scrollHeight;
  }

  function buildCiteCard(c, idx) {
    const card = document.createElement("div");
    card.className = "cite-card";

    const head = document.createElement("div");
    head.className = "cite-head";
    const tag = document.createElement("span");
    tag.className = `tag ${FORMAT_TAGS[c.format] || "txt"}`;
    tag.textContent = c.format;
    const doc = document.createElement("span");
    doc.className = "cite-doc";
    doc.textContent = `[${idx}] ${c.doc_name}`;
    const score = document.createElement("span");
    score.className = "cite-score";
    score.textContent = `匹配度 ${(c.score * 100).toFixed(1)}%`;
    head.append(tag, doc, score);

    const sec = document.createElement("div");
    sec.className = "cite-sec";
    sec.textContent = `章节：${c.section || "—"}` + (c.page ? ` ｜ 第 ${c.page} 页` : "");

    const toggle = document.createElement("button");
    toggle.className = "cite-toggle";
    toggle.textContent = "查看原文片段 ▾";
    toggle.addEventListener("click", () => {
      card.classList.toggle("open");
      toggle.textContent = card.classList.contains("open") ? "收起原文片段 ▴" : "查看原文片段 ▾";
    });

    const src = document.createElement("div");
    src.className = "cite-src";
    src.textContent = c.text;

    card.append(head, sec, toggle, src);
    return card;
  }

  // ---------- 工具 ----------
  function toast(text) {
    const t = document.createElement("div");
    t.textContent = text;
    t.style.cssText = "position:fixed;top:70px;left:50%;transform:translateX(-50%);" +
      "background:#111827;color:#fff;padding:8px 18px;border-radius:8px;font-size:13px;z-index:99;";
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 1800);
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  // ---------- 初始化 ----------
  loadStatus();
  loadDocs();
})();
