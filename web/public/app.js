import { Engine, mulberry32, lineText, sonnetText } from "./engine.js";

const $ = (sel) => document.querySelector(sel);

async function boot() {
  let lexicon;
  try {
    const res = await fetch("lexicon.json");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    lexicon = await res.json();
  } catch (err) {
    $("#sonnet").textContent = `The wordlist could not be loaded (${err.message}). Reload to try again.`;
    return;
  }

  const params = new URLSearchParams(location.search);
  const seedParam = params.get("seed");
  const seed = seedParam !== null ? Number(seedParam) >>> 0
                                  : crypto.getRandomValues(new Uint32Array(1))[0];
  const engine = new Engine(lexicon, mulberry32(seed));
  let sonnet = engine.newSonnet();

  const sonnetEl = $("#sonnet");
  const tpl = $("#line-tpl");

  function render() {
    sonnetEl.replaceChildren();
    for (const line of sonnet.lines) {
      const el = tpl.content.firstElementChild.cloneNode(true);
      if (line.letter === null) {
        el.classList.add("blank");
        el.textContent = " ";
      } else {
        el.textContent = lineText(line);
        el.classList.toggle("frozen", line.frozen);
        const toggle = () => {
          line.frozen = !line.frozen;
          el.classList.toggle("frozen", line.frozen);
        };
        el.addEventListener("click", toggle);
        el.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
        });
      }
      sonnetEl.appendChild(el);
    }
  }

  function newSonnet() {
    sonnet = engine.newSonnet();
    render();
  }
  function rewrite() {
    engine.rewrite(sonnet);
    render();
  }
  function save() {
    const blob = new Blob([sonnetText(sonnet) + "\n"], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "sonnet.txt";
    a.click();
    URL.revokeObjectURL(a.href);
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(sonnetText(sonnet));
    } catch {
      const range = document.createRange();
      range.selectNodeContents(sonnetEl);
      const sel = getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
    }
  }

  // menus
  for (const menu of document.querySelectorAll(".menu")) {
    menu.querySelector(".menu-title").addEventListener("click", (e) => {
      e.stopPropagation();
      const wasOpen = menu.classList.contains("open");
      document.querySelectorAll(".menu.open").forEach(m => m.classList.remove("open"));
      if (!wasOpen) menu.classList.add("open");
    });
  }
  document.addEventListener("click", () =>
    document.querySelectorAll(".menu.open").forEach(m => m.classList.remove("open")));

  $("#mi-new").addEventListener("click", newSonnet);
  $("#mi-save").addEventListener("click", save);
  $("#mi-copy").addEventListener("click", copy);
  $("#mi-about").addEventListener("click", () => $("#about-dialog").showModal());
  $("#mi-help").addEventListener("click", () => $("#help-dialog").showModal());
  $("#pal-rewrite").addEventListener("click", rewrite);
  $("#pal-save").addEventListener("click", save);
  $("#pal-copy").addEventListener("click", copy);
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "n") { e.preventDefault(); newSonnet(); }
    if (e.key === "r" && !e.metaKey && !e.ctrlKey && e.target === document.body) rewrite();
  });

  render();
}

boot();
