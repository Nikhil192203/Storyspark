document.addEventListener("DOMContentLoaded", () => {
  const $ = (id) => document.getElementById(id);
  const form = $("story-form");
  const topicInput = $("topic-input");
  const submitBtn = $("submit-btn");
  const btnText = submitBtn.querySelector(".btn-text");
  const spinner = submitBtn.querySelector(".btn-spinner");
  const state = { topic: "", age: 8, objectives: [], questions: [], answers: {}, followUpQuestions: [], report: null };
  const PEDAGOGY = { "4-6": "Playful discovery", "7-9": "Story-based adventure", "10-12": "Problem-solving story", "13-14": "Real-world inquiry" };

  function ageBand(age) { return age <= 6 ? "4-6" : age <= 9 ? "7-9" : age <= 12 ? "10-12" : "13-14"; }
  function setJourney(step) { document.querySelectorAll(".journey-step").forEach((item) => item.classList.toggle("active", item.dataset.step === step)); }
  function show(el) { el.classList.remove("hidden"); }
  function hide(el) { el.classList.add("hidden"); }
  function notice(kind, message) { $("error-banner-message").textContent = message; kind === "error" ? show($("error-banner")) : (($("info-banner-message").textContent = message), show($("info-banner"))); }
  function clearNotices() { hide($("error-banner")); hide($("info-banner")); }
  function statusLabel(status) { return status === "mastered" ? "🟢 Mastered" : status === "developing" ? "🟡 Developing" : "🔴 Needs reinforcement"; }
  function responseError(response, fallback) { return response.json().then((body) => body.detail || fallback).catch(() => fallback); }

  async function health() {
    try {
      const response = await fetch("/api/health"); const data = await response.json();
      $("backend-status").replaceChildren(); const dot = document.createElement("span"); dot.className = `status-dot ${data.gemini_configured ? "online" : "offline"}`; dot.setAttribute("aria-hidden", "true");
      $("backend-status").append(dot, document.createTextNode(data.gemini_configured ? "Ready to create" : "Service setup needed"));
    } catch { $("backend-status").textContent = "Service unavailable"; }
  }

  function updateSettings() { const age = Number(document.querySelector('input[name="child_age"]:checked').value); $("setting-age").textContent = `${age} years`; $("setting-style").textContent = PEDAGOGY[ageBand(age)]; }
  topicInput.addEventListener("input", () => { $("topic-char-count").textContent = `${topicInput.value.length} / 100`; hide($("topic-error")); });
  document.querySelectorAll(".topic-chip").forEach((button) => button.addEventListener("click", () => { topicInput.value = button.dataset.topic; topicInput.dispatchEvent(new Event("input")); topicInput.focus(); }));
  document.querySelectorAll('input[name="child_age"]').forEach((input) => input.addEventListener("change", updateSettings));
  $("error-banner-close").addEventListener("click", () => hide($("error-banner")));

  function validateStoryForm() {
    const topic = topicInput.value.trim(); const age = Number(document.querySelector('input[name="child_age"]:checked')?.value);
    if (topic.length < 2 || !/[a-zA-Z0-9]/.test(topic)) { $("topic-error").textContent = "Enter a meaningful topic with at least 2 characters."; show($("topic-error")); topicInput.focus(); return null; }
    return { topic, age };
  }

  function splitScenes(story) {
    const paragraphs = story.split(/\n\s*\n/).filter(Boolean);
    if (paragraphs.length > 1) return paragraphs;
    const sentences = story.match(/[^.!?]+[.!?]+(?:\s|$)/g) || [story];
    const count = Math.min(3, Math.max(1, Math.ceil(sentences.length / 3)));
    const size = Math.ceil(sentences.length / count);
    return Array.from({ length: count }, (_, index) => sentences.slice(index * size, (index + 1) * size).join(" ").trim()).filter(Boolean);
  }

  function renderStory(data) {
    $("story-topic-badge").textContent = state.topic; $("story-age-badge").textContent = `Age ${state.age}`; $("story-tier-badge").textContent = PEDAGOGY[ageBand(state.age)];
    $("story-body").replaceChildren(); splitScenes(data.story).forEach((scene, index) => { const section = document.createElement("section"); section.className = "scene-card"; const heading = document.createElement("h4"); heading.textContent = `📖 Scene ${index + 1}`; const paragraph = document.createElement("p"); paragraph.textContent = scene; section.append(heading, paragraph); $("story-body").appendChild(section); });
    $("learning-objectives-list").replaceChildren(); data.learning_objectives.forEach((item) => { const li = document.createElement("li"); li.textContent = item; $("learning-objectives-list").appendChild(li); });
    $("key-concepts-container").replaceChildren(); data.key_concepts.forEach((item) => { const tag = document.createElement("span"); tag.textContent = item; $("key-concepts-container").appendChild(tag); });
  }

  function updateProgress(questions, formElement, target) {
    const answered = questions.filter((question) => formElement.querySelector(`[name="${question.id}"]:checked`) || formElement.elements.namedItem(question.id)?.value.trim()).length;
    target.textContent = `Question ${Math.min(answered + 1, questions.length)} of ${questions.length}`;
  }

  function renderQuestions(questions, container, formElement, progressTarget = null) {
    container.replaceChildren();
    questions.forEach((question, index) => {
      const fieldset = document.createElement("fieldset"); fieldset.className = "question-card";
      const legend = document.createElement("legend"); legend.textContent = `${index + 1}. ${question.question}`; fieldset.appendChild(legend);
      if (question.type === "Short Answer") {
        const label = document.createElement("label"); label.htmlFor = `${question.id}-answer`; label.textContent = `Your answer about ${question.concept}`;
        const input = document.createElement("input"); input.id = `${question.id}-answer`; input.name = question.id; input.required = true; input.addEventListener("input", () => progressTarget && updateProgress(questions, formElement, progressTarget)); fieldset.append(label, input);
      } else {
        const options = document.createElement("div"); options.className = "answer-options";
        question.options.forEach((option, optionIndex) => { const id = `${question.id}-${optionIndex}`; const label = document.createElement("label"); const input = document.createElement("input"); input.type = "radio"; input.id = id; input.name = question.id; input.value = option; input.required = true; input.addEventListener("change", () => progressTarget && updateProgress(questions, formElement, progressTarget)); const text = document.createElement("span"); text.textContent = option; label.htmlFor = id; label.append(input, text); options.appendChild(label); });
        fieldset.appendChild(options);
      }
      container.appendChild(fieldset);
    });
    if (progressTarget) updateProgress(questions, formElement, progressTarget);
  }

  function collectAnswers(questions, formElement) { return Object.fromEntries(questions.map((question) => { const selected = formElement.querySelector(`[name="${question.id}"]:checked`) || formElement.elements.namedItem(question.id); return [question.id, selected?.value.trim() || ""]; })); }
  function reportPayload(answers) { return { topic: state.topic, age: state.age, learning_objectives: state.objectives, questions: state.questions, answers }; }

  function reportItem(title, content) { const section = document.createElement("section"); section.className = "report-item"; const h3 = document.createElement("h3"); h3.textContent = title; const p = document.createElement("p"); p.textContent = content; section.append(h3, p); return section; }
  function renderReport(report) {
    state.report = report; setJourney("report"); $("report-topic-age").textContent = `${report.topic} · Age ${report.age}`;
    const content = $("report-content"); content.replaceChildren(); const score = document.createElement("section"); score.className = "score-card"; score.innerHTML = `<span>Overall understanding</span><strong>${report.percentage}%</strong><p>${report.correct} of ${report.total} correct</p><div class="progress-track"><span style="width:${report.percentage}%"></span></div>`; content.appendChild(score);
    const objectives = document.createElement("section"); objectives.className = "report-item"; const h = document.createElement("h3"); h.textContent = "Learning objectives"; const list = document.createElement("ul"); state.objectives.forEach((objective, index) => { const li = document.createElement("li"); li.textContent = `${statusLabel(report.objective_coverage[index])} — ${objective}`; list.appendChild(li); }); objectives.append(h, list); content.appendChild(objectives);
    const concepts = document.createElement("section"); concepts.className = "report-item"; const conceptHeading = document.createElement("h3"); conceptHeading.textContent = "Concept mastery"; const conceptList = document.createElement("ul"); report.concept_results.forEach((result) => { const li = document.createElement("li"); li.textContent = `${statusLabel(result.status)} — ${result.concept} (${result.correct}/${result.total})`; conceptList.appendChild(li); }); concepts.append(conceptHeading, conceptList); content.appendChild(concepts);
    content.append(reportItem("What the learner understood", report.summary), reportItem("Recommended next step", report.recommended_next_step));
    const teacher = $("teacher-content"); teacher.replaceChildren(); teacher.append(reportItem("Overall understanding", `${report.percentage}% (${report.correct}/${report.total})`), reportItem("Strengths and knowledge gaps", report.concept_results.map((item) => `${item.concept}: ${item.status}`).join(" · ")), reportItem("Recommended next step", report.recommended_next_step));
    const gaps = report.concept_results.filter((item) => item.status !== "mastered"); const action = $("reinforcement-action"); action.replaceChildren();
    if (gaps.length) { const text = document.createElement("p"); text.textContent = `Targeted support is available for: ${gaps.map((item) => item.concept).join(", ")}.`; const button = document.createElement("button"); button.className = "primary-button"; button.type = "button"; button.textContent = "✨ Reinforce My Gaps"; button.addEventListener("click", generateReinforcement); action.append(text, button); } else { const success = document.createElement("p"); success.className = "great-work"; success.textContent = "🎉 Great work! You demonstrated strong understanding of the key concepts."; action.appendChild(success); }
    show($("learning-report")); $("learning-report").focus();
  }

  async function generateReinforcement() {
    const action = $("reinforcement-action"); const button = action.querySelector("button"); button.disabled = true; button.textContent = "Creating targeted support…";
    try { const response = await fetch("/api/reinforcement/generate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(reportPayload(state.answers)) }); if (!response.ok) throw new Error(await responseError(response, "Unable to create reinforcement.")); const data = await response.json(); renderReinforcement(data); } catch (error) { notice("error", error.message); button.disabled = false; button.textContent = "✨ Reinforce My Gaps"; }
  }

  function renderReinforcement(data) {
    setJourney("reinforce"); const content = $("reinforcement-content"); content.replaceChildren(); const heading = document.createElement("h3"); heading.textContent = `A focused mini-lesson: ${data.gap_concepts.join(", ")}`; const text = document.createElement("p"); text.textContent = data.teaching_text; content.append(heading, text);
    state.followUpQuestions = data.questions; const followUp = $("follow-up-form"); renderQuestions(data.questions, $("follow-up-questions"), followUp); show(followUp); show($("reinforcement-section")); $("reinforcement-section").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault(); clearNotices(); const input = validateStoryForm(); if (!input) return;
    state.topic = input.topic; state.age = input.age; submitBtn.disabled = true; spinner.classList.remove("hidden"); btnText.textContent = "Creating your story…"; show($("loading-state")); hide($("story-display-section")); hide($("learning-report")); hide($("reinforcement-section"));
    try { const response = await fetch("/api/story/generate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) }); if (!response.ok) throw new Error(await responseError(response, "Unable to create a story.")); const data = await response.json(); state.objectives = data.learning_objectives; state.questions = data.questions; state.answers = {}; renderStory(data); renderQuestions(data.questions, $("assessment-questions"), $("assessment-form"), $("assessment-progress")); setJourney("check"); show($("story-display-section")); $("story-display-section").scrollIntoView({ behavior: "smooth", block: "start" }); notice("success", "Your learning adventure is ready."); } catch (error) { notice("error", error.message); } finally { submitBtn.disabled = false; spinner.classList.add("hidden"); btnText.textContent = "Create my story"; hide($("loading-state")); }
  });

  $("assessment-form").addEventListener("submit", async (event) => { event.preventDefault(); state.answers = collectAnswers(state.questions, $("assessment-form")); if (Object.values(state.answers).some((answer) => !answer)) { $("assessment-error").textContent = "Answer every question to see the complete report."; show($("assessment-error")); return; } hide($("assessment-error")); try { const response = await fetch("/api/assessment/report", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(reportPayload(state.answers)) }); if (!response.ok) throw new Error(await responseError(response, "Unable to build learning report.")); renderReport(await response.json()); } catch (error) { $("assessment-error").textContent = error.message; show($("assessment-error")); } });

  $("follow-up-form").addEventListener("submit", async (event) => { event.preventDefault(); const answers = collectAnswers(state.followUpQuestions, $("follow-up-form")); if (Object.values(answers).some((answer) => !answer)) { $("follow-up-error").textContent = "Answer every follow-up question first."; show($("follow-up-error")); return; } try { const response = await fetch("/api/assessment/score", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ questions: state.followUpQuestions, answers }) }); if (!response.ok) throw new Error(await responseError(response, "Unable to score follow-up.")); const score = await response.json(); const result = $("follow-up-report"); result.replaceChildren(); const h = document.createElement("h3"); h.textContent = `Updated understanding: ${score.percentage}%`; const p = document.createElement("p"); p.textContent = score.percentage === 100 ? "Excellent—your follow-up answers demonstrate stronger understanding." : "Keep practicing—the follow-up identifies what to revisit next."; result.append(h, p); show(result); hide($("follow-up-error")); } catch (error) { $("follow-up-error").textContent = error.message; show($("follow-up-error")); } });

  $("create-another-btn").addEventListener("click", () => { form.scrollIntoView({ behavior: "smooth", block: "start" }); topicInput.focus(); setJourney("create"); });
  health(); updateSettings();
});