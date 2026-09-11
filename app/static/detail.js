(function () {
  const tagChipsEl = document.getElementById("tag-chips");
  const newTagInput = document.getElementById("new-tag");
  const addTagBtn = document.getElementById("add-tag-btn");
  const newFolderInput = document.getElementById("new-folder");
  const addFolderBtn = document.getElementById("add-folder-btn");
  const folderCheckboxes = document.getElementById("folder-checkboxes");
  const saveBtn = document.getElementById("save-btn");
  const deleteBtn = document.getElementById("delete-btn");
  const statusEl = document.getElementById("status");

  let tags = JSON.parse(tagChipsEl.dataset.tags || "[]");

  function showStatus(message, isError) {
    statusEl.hidden = false;
    statusEl.textContent = message;
    statusEl.classList.toggle("error", !!isError);
  }

  function renderChips() {
    tagChipsEl.innerHTML = "";
    tags.forEach((tag) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = tag;
      chip.title = "Click to remove";
      chip.addEventListener("click", () => {
        tags = tags.filter((t) => t !== tag);
        renderChips();
      });
      tagChipsEl.appendChild(chip);
    });
  }

  function addTag(raw) {
    const tag = raw.trim().toLowerCase();
    if (tag && !tags.includes(tag)) {
      tags.push(tag);
      renderChips();
    }
  }

  function addFolderCheckbox(name) {
    const existing = [...folderCheckboxes.querySelectorAll("input[name=folder]")]
      .map((el) => el.value.toLowerCase());
    if (existing.includes(name.toLowerCase())) return;

    const label = document.createElement("label");
    label.className = "checkbox";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "folder";
    input.value = name;
    input.checked = true;
    label.appendChild(input);
    label.append(" " + name);
    folderCheckboxes.appendChild(label);
  }

  addTagBtn.addEventListener("click", () => {
    addTag(newTagInput.value);
    newTagInput.value = "";
    newTagInput.focus();
  });
  newTagInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addTagBtn.click();
    }
  });

  addFolderBtn.addEventListener("click", () => {
    const name = newFolderInput.value.trim();
    if (name) addFolderCheckbox(name);
    newFolderInput.value = "";
    newFolderInput.focus();
  });
  newFolderInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addFolderBtn.click();
    }
  });

  saveBtn.addEventListener("click", async () => {
    const folders = [...folderCheckboxes.querySelectorAll("input[name=folder]:checked")]
      .map((el) => el.value);

    showStatus("Saving…");
    try {
      const resp = await fetch(`/photos/${window.PHOTO_ID}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tags, folders }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Save failed");
      showStatus("Saved.");
    } catch (err) {
      showStatus(err.message, true);
    }
  });

  deleteBtn.addEventListener("click", async () => {
    if (!confirm("Delete this photo permanently?")) return;

    showStatus("Deleting…");
    try {
      const resp = await fetch(`/photos/${window.PHOTO_ID}`, { method: "DELETE" });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Delete failed");
      window.location.href = "/";
    } catch (err) {
      showStatus(err.message, true);
    }
  });

  renderChips();
})();
