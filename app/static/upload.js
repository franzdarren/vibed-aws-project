(function () {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const statusEl = document.getElementById("status");
  const resultEl = document.getElementById("result");
  const preview = document.getElementById("preview");
  const tagChips = document.getElementById("tag-chips");
  const newTagInput = document.getElementById("new-tag");
  const addTagBtn = document.getElementById("add-tag-btn");
  const newFolderInput = document.getElementById("new-folder");
  const addFolderBtn = document.getElementById("add-folder-btn");
  const folderCheckboxes = document.getElementById("folder-checkboxes");
  const saveBtn = document.getElementById("save-btn");
  const discardBtn = document.getElementById("discard-btn");

  let tags = [];
  let uploadInfo = null; // { s3_key, s3_url, ai_suggested_tags }

  // Best-effort cleanup of a classified-but-never-saved S3 object (user
  // changed their mind, replaced the file, or is navigating away).
  function discardUpload(key) {
    return fetch("/uploads/discard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ s3_key: key }),
    }).catch(() => {});
  }

  window.addEventListener("beforeunload", () => {
    if (uploadInfo) {
      const blob = new Blob([JSON.stringify({ s3_key: uploadInfo.s3_key })], {
        type: "application/json",
      });
      navigator.sendBeacon("/uploads/discard", blob);
    }
  });

  function showStatus(message, isError) {
    statusEl.hidden = false;
    statusEl.textContent = message;
    statusEl.classList.toggle("error", !!isError);
  }

  function renderChips() {
    tagChips.innerHTML = "";
    tags.forEach((tag) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = tag;
      chip.title = "Click to remove";
      chip.addEventListener("click", () => {
        tags = tags.filter((t) => t !== tag);
        renderChips();
      });
      tagChips.appendChild(chip);
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

  async function handleFile(file) {
    if (!file) return;
    if (!/\.(jpe?g|png)$/i.test(file.name)) {
      showStatus("Only .jpg/.jpeg/.png files are allowed.", true);
      return;
    }

    if (uploadInfo) {
      // Replacing a photo that was classified but never saved — clean up
      // the orphaned S3 object instead of leaving it behind.
      discardUpload(uploadInfo.s3_key);
      uploadInfo = null;
    }

    preview.src = URL.createObjectURL(file);
    showStatus("Classifying photo…");
    resultEl.hidden = true;

    const formData = new FormData();
    formData.append("photo", file);

    try {
      const resp = await fetch("/upload", { method: "POST", body: formData });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Upload failed");

      uploadInfo = data;
      tags = [...data.ai_suggested_tags];
      renderChips();
      resultEl.hidden = false;
      showStatus("Classified! Review the tags and folders below, then save.");
    } catch (err) {
      showStatus(err.message, true);
    }
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
    handleFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener("change", () => handleFile(fileInput.files[0]));

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
    if (!uploadInfo) return;

    const folders = [...folderCheckboxes.querySelectorAll("input[name=folder]:checked")]
      .map((el) => el.value);

    showStatus("Saving…");
    try {
      const resp = await fetch("/photos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          s3_key: uploadInfo.s3_key,
          s3_url: uploadInfo.s3_url,
          ai_suggested_tags: uploadInfo.ai_suggested_tags,
          tags,
          folders,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Save failed");

      uploadInfo = null; // saved now — don't let beforeunload discard it
      window.location.href = "/";
    } catch (err) {
      showStatus(err.message, true);
    }
  });

  discardBtn.addEventListener("click", async () => {
    if (!uploadInfo) return;
    showStatus("Discarding…");
    await discardUpload(uploadInfo.s3_key);
    uploadInfo = null;
    tags = [];
    resultEl.hidden = true;
    fileInput.value = "";
    showStatus("Discarded. Upload another photo whenever you're ready.");
  });
})();
