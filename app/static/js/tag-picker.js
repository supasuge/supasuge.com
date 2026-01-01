/**
 * Vanilla JS Tag Picker with Autocomplete
 * Usage: <div class="tag-picker" data-selected-tags='["tag1", "tag2"]'></div>
 *
 * Security goals:
 * - Never inject untrusted text with innerHTML
 * - Use textContent + dataset + DOM creation
 * - Keep hidden input consistent
 */

class TagPicker {
  constructor(element) {
    this.element = element;
    this.selectedTags = this.safeParseTags(element.dataset.selectedTags);
    this.render();
    this.attachEvents();
  }

  safeParseTags(raw) {
    try {
      const v = JSON.parse(raw || "[]");
      if (Array.isArray(v)) return v.filter(t => typeof t === "string");
    } catch (_) {}
    return [];
  }

  render() {
    this.element.innerHTML = "";

    const container = document.createElement("div");
    container.className = "tag-picker-container";

    const chips = document.createElement("div");
    chips.className = "tag-chips";

    const inputWrap = document.createElement("div");
    inputWrap.className = "tag-input-wrapper";

    const input = document.createElement("input");
    input.type = "text";
    input.className = "tag-input";
    input.placeholder = "Add tags...";
    input.autocomplete = "off";

    const dropdown = document.createElement("div");
    dropdown.className = "tag-dropdown";
    dropdown.style.display = "none";

    const hidden = document.createElement("input");
    hidden.type = "hidden";
    hidden.name = "tag_slugs";
    hidden.value = this.selectedTags.join(",");

    inputWrap.appendChild(input);
    inputWrap.appendChild(dropdown);

    container.appendChild(chips);
    container.appendChild(inputWrap);
    container.appendChild(hidden);

    this.element.appendChild(container);

    this.updateChips();
  }

  updateChips() {
    const chipsContainer = this.element.querySelector(".tag-chips");
    chipsContainer.textContent = "";

    for (const tag of this.selectedTags) {
      const chip = document.createElement("span");
      chip.className = "tag-chip";
      chip.dataset.tag = tag;

      const text = document.createElement("span");
      text.textContent = tag;

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tag-remove";
      btn.dataset.tag = tag;
      btn.textContent = "×";

      chip.appendChild(text);
      chip.appendChild(btn);
      chipsContainer.appendChild(chip);
    }

    const hidden = this.element.querySelector('input[name="tag_slugs"]');
    hidden.value = this.selectedTags.join(",");
  }

  attachEvents() {
    const input = this.element.querySelector(".tag-input");
    const dropdown = this.element.querySelector(".tag-dropdown");

    let timeout;

    input.addEventListener("input", (e) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => this.search(e.target.value), 250);
    });

    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        this.addTag(input.value.trim());
        input.value = "";
        dropdown.style.display = "none";
      }
      if (e.key === "Escape") {
        dropdown.style.display = "none";
      }
    });

    this.element.addEventListener("click", (e) => {
      if (e.target && e.target.classList && e.target.classList.contains("tag-remove")) {
        this.removeTag(e.target.dataset.tag);
      }
      if (e.target && e.target.classList && e.target.classList.contains("tag-suggestion")) {
        this.addTag(e.target.dataset.tag);
        input.value = "";
        dropdown.style.display = "none";
      }
    });

    input.addEventListener("blur", () => {
      setTimeout(() => { dropdown.style.display = "none"; }, 150);
    });
  }

  async search(query) {
    const dropdown = this.element.querySelector(".tag-dropdown");
    const q = (query || "").trim();

    dropdown.textContent = "";
    dropdown.style.display = "none";

    if (!q) return;

    try {
      const res = await fetch(`/admin/tags/search?q=${encodeURIComponent(q)}`, {
        method: "GET",
        credentials: "same-origin",
        headers: { "Accept": "application/json" },
      });

      if (!res.ok) return;

      const tags = await res.json();
      const safeTags = Array.isArray(tags) ? tags.filter(t => typeof t === "string") : [];

      if (safeTags.length === 0) {
        const hint = document.createElement("div");
        hint.className = "tag-suggestion-new";
        hint.textContent = `Press Enter to create "${q}"`;
        dropdown.appendChild(hint);
      } else {
        for (const t of safeTags) {
          if (this.selectedTags.includes(t)) continue;
          const opt = document.createElement("div");
          opt.className = "tag-suggestion";
          opt.dataset.tag = t;
          opt.textContent = t;
          dropdown.appendChild(opt);
        }
      }

      dropdown.style.display = "block";
    } catch (err) {
      // Keep failures quiet; admin page should still function without autocomplete.
      console.error("Tag search failed:", err);
    }
  }

  addTag(tag) {
    const t = (tag || "").trim();
    if (!t) return;
    if (this.selectedTags.includes(t)) return;

    this.selectedTags.push(t);
    this.updateChips();
  }

  removeTag(tag) {
    const t = (tag || "").trim();
    if (!t) return;

    this.selectedTags = this.selectedTags.filter(x => x !== t);
    this.updateChips();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".tag-picker").forEach(el => new TagPicker(el));
});
