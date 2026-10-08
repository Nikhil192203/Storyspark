/**
 * StorySpark Application Client Logic
 * Provides accessible controls, real-time validation, Google Gemini integration,
 * and loading/error state management.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const form = document.getElementById("story-form");
  const topicInput = document.getElementById("topic-input");
  const topicCharCount = document.getElementById("topic-char-count");
  const topicError = document.getElementById("topic-error");
  const ageRadios = document.querySelectorAll('input[name="child_age"]');
  const ageError = document.getElementById("age-error");
  const submitBtn = document.getElementById("submit-btn");
  const btnSpinner = submitBtn.querySelector(".btn-spinner");
  const btnText = submitBtn.querySelector(".btn-text");

  // Status & Feedback banners
  const backendStatusEl = document.getElementById("backend-status");
  const errorBanner = document.getElementById("error-banner");
  const errorBannerMessage = document.getElementById("error-banner-message");
  const errorBannerClose = document.getElementById("error-banner-close");
  const infoBanner = document.getElementById("info-banner");
  const infoBannerMessage = document.getElementById("info-banner-message");

  // Pedagogy preview cards
  const pedagogyTier = document.getElementById("pedagogy-tier");
  const pedagogyComplexity = document.getElementById("pedagogy-complexity");
  const pedagogyStyle = document.getElementById("pedagogy-style");

  // Loading state
  const loadingState = document.getElementById("loading-state");

  // Story presentation elements
  const storyDisplaySection = document.getElementById("story-display-section");
  const storyTopicBadge = document.getElementById("story-topic-badge");
  const storyAgeBadge = document.getElementById("story-age-badge");
  const storyTierBadge = document.getElementById("story-tier-badge");
  const storyBody = document.getElementById("story-body");
  const learningObjectivesList = document.getElementById("learning-objectives-list");
  const keyConceptsContainer = document.getElementById("key-concepts-container");
  const createAnotherBtn = document.getElementById("create-another-btn");
  const assessmentForm = document.getElementById("assessment-form");
  const assessmentQuestions = document.getElementById("assessment-questions");
  const assessmentProgress = document.getElementById("assessment-progress");
  const assessmentError = document.getElementById("assessment-error");
  const assessmentResults = document.getElementById("assessment-results");
  let currentQuestions = [];

  // Topic suggestion chips
  const topicChips = document.querySelectorAll(".topic-chip");

  // Pedagogy guidance mapping
  const PEDAGOGY_DATA = {
    "4-6": {
      tier: "Early Explorer (Ages 4–6)",
      complexity: "Foundational / Intuitive",
      style: "Playful metaphors, sensory descriptions, vibrant characters, and simple everyday scenarios without technical jargon.",
    },
    "7-9": {
      tier: "Curious Adventurer (Ages 7–9)",
      complexity: "Intermediate / Exploratory",
      style: "Exciting quests, dialogue, relatable challenges, and tangible cause-and-effect science.",
    },
    "10-12": {
      tier: "Bold Discoverer (Ages 10–12)",
      complexity: "Advanced / Analytical",
      style: "Deeper scientific mechanisms, narrative stakes, mathematical reasoning, and problem-solving puzzles.",
    },
    "13-14": {
      tier: "Young Innovator (Ages 13–14)",
      complexity: "Proficient / Systematic",
      style: "Nuanced inquiry, systemic connections, real-world applications, and higher-order critical thinking.",
    },
  };

  /**
   * Determine age band key for given age number
   */
  function getAgeBand(age) {
    if (age <= 6) return "4-6";
    if (age <= 9) return "7-9";
    if (age <= 12) return "10-12";
    return "13-14";
  }

  /**
   * Update pedagogy insight card when age changes
   */
  function updatePedagogyGuidance(age) {
    const band = getAgeBand(age);
    const data = PEDAGOGY_DATA[band];
    if (data) {
      pedagogyTier.textContent = data.tier;
      pedagogyComplexity.textContent = data.complexity;
      pedagogyStyle.textContent = data.style;
    }
  }

  /**
   * Check backend health and update status dot
   */
  async function checkBackendHealth() {
    try {
      const response = await fetch("/api/health");
      if (response.ok) {
        const data = await response.json();
        const geminiStatus = data.gemini_configured ? "Gemini Ready" : "Gemini Key Missing";
        backendStatusEl.innerHTML = `
          <span class="status-dot ${data.gemini_configured ? 'status-online' : 'status-unknown'}" aria-hidden="true"></span>
          <span class="status-text">Backend Active &bull; ${geminiStatus}</span>
        `;
      } else {
        throw new Error("Backend returned status " + response.status);
      }
    } catch (err) {
      backendStatusEl.innerHTML = `
        <span class="status-dot status-offline" aria-hidden="true"></span>
        <span class="status-text">Backend Disconnected</span>
      `;
    }
  }

  // Initial health check
  checkBackendHealth();

  /**
   * Character counter for topic input
   */
  function updateCharCount() {
    const len = topicInput.value.length;
    topicCharCount.textContent = `${len} / 100`;
  }

  topicInput.addEventListener("input", () => {
    updateCharCount();
    clearFieldError(topicInput, topicError);
  });

  /**
   * Quick chip clicks
   */
  topicChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      topicInput.value = chip.dataset.topic;
      updateCharCount();
      clearFieldError(topicInput, topicError);
      topicInput.focus();
    });
  });

  /**
   * Age radio selection listener
   */
  ageRadios.forEach((radio) => {
    radio.addEventListener("change", () => {
      const selectedAge = parseInt(radio.value, 10);
      updatePedagogyGuidance(selectedAge);
      clearFieldError(null, ageError);
    });
  });

  /**
   * Show error for a specific field
   */
  function setFieldError(inputEl, errorEl, message) {
    if (inputEl) {
      inputEl.classList.add("has-error");
      inputEl.setAttribute("aria-invalid", "true");
    }
    if (errorEl) {
      errorEl.textContent = message;
      errorEl.classList.remove("hidden");
    }
  }

  /**
   * Clear error for a specific field
   */
  function clearFieldError(inputEl, errorEl) {
    if (inputEl) {
      inputEl.classList.remove("has-error");
      inputEl.removeAttribute("aria-invalid");
    }
    if (errorEl) {
      errorEl.textContent = "";
      errorEl.classList.add("hidden");
    }
  }

  /**
   * Show global error banner
   */
  function showErrorBanner(message) {
    errorBannerMessage.textContent = message;
    errorBanner.classList.remove("hidden");
    errorBanner.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  /**
   * Hide global error banner
   */
  function hideErrorBanner() {
    errorBanner.classList.add("hidden");
  }

  errorBannerClose.addEventListener("click", hideErrorBanner);

  /**
   * Show info banner
   */
  function showInfoBanner(message) {
    infoBannerMessage.textContent = message;
    infoBanner.classList.remove("hidden");
  }

  function hideInfoBanner() {
    infoBanner.classList.add("hidden");
  }

  /**
   * Validate fields locally before submission
   */
  function validateLocal() {
    let isValid = true;
    hideErrorBanner();
    hideInfoBanner();

    // Validate Topic
    const topicVal = topicInput.value.trim();
    if (!topicVal) {
      setFieldError(topicInput, topicError, "Please enter a school topic (e.g. Gravity, Fractions).");
      isValid = false;
    } else if (topicVal.length < 2) {
      setFieldError(topicInput, topicError, "Topic must be at least 2 characters long.");
      isValid = false;
    } else if (topicVal.length > 100) {
      setFieldError(topicInput, topicError, "Topic cannot exceed 100 characters.");
      isValid = false;
    } else if (!/[a-zA-Z0-9]/.test(topicVal)) {
      setFieldError(topicInput, topicError, "Topic must contain readable words or numbers.");
      isValid = false;
    } else {
      clearFieldError(topicInput, topicError);
    }

    // Validate Age
    const selectedRadio = document.querySelector('input[name="child_age"]:checked');
    if (!selectedRadio) {
      setFieldError(null, ageError, "Please select the child's age.");
      isValid = false;
    } else {
      const ageNum = parseInt(selectedRadio.value, 10);
      if (isNaN(ageNum) || ageNum < 4 || ageNum > 14) {
        setFieldError(null, ageError, "Age must be between 4 and 14 years.");
        isValid = false;
      } else {
        clearFieldError(null, ageError);
      }
    }

    return isValid;
  }

  function updateAssessmentProgress() {
    const answered = currentQuestions.filter((question) => {
      const input = assessmentForm.elements.namedItem(question.id);
      return input && ((input.value || "").trim() || [...assessmentForm.querySelectorAll(`input[name="${question.id}"]`)].some((option) => option.checked));
    }).length;
    assessmentProgress.textContent = `Question ${Math.min(answered + 1, currentQuestions.length)} of ${currentQuestions.length}`;
  }

  function renderAssessment(questions) {
    currentQuestions = questions;
    assessmentQuestions.replaceChildren();
    assessmentError.classList.add("hidden");
    assessmentResults.classList.add("hidden");

    questions.forEach((question, index) => {
      const fieldset = document.createElement("fieldset");
      fieldset.className = "assessment-question";
      const legend = document.createElement("legend");
      legend.textContent = `${index + 1}. ${question.question}`;
      fieldset.appendChild(legend);

      if (question.type === "Short Answer") {
        const label = document.createElement("label");
        label.htmlFor = `answer-${question.id}`;
        label.textContent = `Your answer about ${question.concept}`;
        const input = document.createElement("input");
        input.id = `answer-${question.id}`;
        input.name = question.id;
        input.className = "form-input";
        input.type = "text";
        input.required = true;
        input.addEventListener("input", updateAssessmentProgress);
        fieldset.append(label, input);
      } else {
        const options = document.createElement("div");
        options.className = "answer-options";
        question.options.forEach((option, optionIndex) => {
          const optionId = `answer-${question.id}-${optionIndex}`;
          const label = document.createElement("label");
          label.className = "answer-option";
          const input = document.createElement("input");
          input.id = optionId;
          input.name = question.id;
          input.type = "radio";
          input.value = option;
          input.required = true;
          input.addEventListener("change", updateAssessmentProgress);
          const text = document.createElement("span");
          text.textContent = option;
          label.append(input, text);
          options.appendChild(label);
        });
        fieldset.appendChild(options);
      }
      assessmentQuestions.appendChild(fieldset);
    });
    updateAssessmentProgress();
  }

  function getAssessmentAnswers() {
    return Object.fromEntries(currentQuestions.map((question) => {
      const selected = assessmentForm.querySelector(`[name="${question.id}"]:checked`) || assessmentForm.elements.namedItem(question.id);
      return [question.id, selected?.value?.trim() || ""];
    }));
  }

  function displayAssessmentResults(result) {
    assessmentResults.replaceChildren();
    const heading = document.createElement("h5");
    heading.textContent = `Score: ${result.correct} of ${result.total} (${result.percentage}%)`;
    const list = document.createElement("ul");
    result.concept_results.forEach((concept) => {
      const item = document.createElement("li");
      item.textContent = `${concept.concept}: ${concept.status} (${concept.correct}/${concept.total})`;
      list.appendChild(item);
    });
    assessmentResults.append(heading, list);
    assessmentResults.classList.remove("hidden");
  }

  /**
   * Render story content safely
   */
  function displayStory(topic, age, data) {
    storyTopicBadge.textContent = topic;
    storyAgeBadge.textContent = `${age} Years Old`;
    const band = getAgeBand(age);
    storyTierBadge.textContent = PEDAGOGY_DATA[band]?.tier || `${age} Years`;

    // Render paragraphs
    storyBody.innerHTML = "";
    const rawStory = data.story || "";
    const paragraphs = rawStory.split(/\n\s*\n/).filter((p) => p.trim().length > 0);

    if (paragraphs.length > 0) {
      paragraphs.forEach((paragraphText) => {
        const p = document.createElement("p");
        p.textContent = paragraphText.trim();
        storyBody.appendChild(p);
      });
    } else {
      const p = document.createElement("p");
      p.textContent = rawStory;
      storyBody.appendChild(p);
    }

    // Render learning objectives
    learningObjectivesList.innerHTML = "";
    if (Array.isArray(data.learning_objectives)) {
      data.learning_objectives.forEach((obj) => {
        const li = document.createElement("li");
        li.textContent = obj;
        learningObjectivesList.appendChild(li);
      });
    }

    // Render key concepts
    keyConceptsContainer.innerHTML = "";
    if (Array.isArray(data.key_concepts)) {
      data.key_concepts.forEach((concept) => {
        const tag = document.createElement("span");
        tag.className = "concept-tag";
        tag.textContent = concept;
        keyConceptsContainer.appendChild(tag);
      });
    }

    renderAssessment(data.questions);
    storyDisplaySection.classList.remove("hidden");
    storyDisplaySection.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  assessmentForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const answers = getAssessmentAnswers();
    if (Object.values(answers).some((answer) => !answer)) {
      assessmentError.textContent = "Please answer every question before submitting.";
      assessmentError.classList.remove("hidden");
      return;
    }
    assessmentError.classList.add("hidden");

    try {
      const response = await fetch("/api/assessment/score", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ questions: currentQuestions, answers }),
      });
      if (!response.ok) {
        throw new Error("Unable to score the assessment.");
      }
      displayAssessmentResults(await response.json());
    } catch (error) {
      assessmentError.textContent = error.message || "Unable to score the assessment.";
      assessmentError.classList.remove("hidden");
    }
  });

  /**
   * Form submit handler -> Calls REAL Gemini story generation
   */
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (!validateLocal()) {
      showErrorBanner("Please correct the errors in the form before continuing.");
      return;
    }

    const topic = topicInput.value.trim();
    const age = parseInt(document.querySelector('input[name="child_age"]:checked').value, 10);

    // Enter loading state
    submitBtn.disabled = true;
    submitBtn.setAttribute("aria-busy", "true");
    btnSpinner.classList.remove("hidden");
    btnText.textContent = "Creating Your Story with Gemini...";
    loadingState.classList.remove("hidden");
    loadingState.setAttribute("aria-hidden", "false");
    storyDisplaySection.classList.add("hidden");
    hideErrorBanner();
    hideInfoBanner();

    try {
      const response = await fetch("/api/story/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ topic, age }),
      });

      if (!response.ok) {
        let errorDetail = "Failed to generate story.";
        try {
          const errorData = await response.json();
          errorDetail = errorData.detail || errorDetail;
        } catch (_) {
          errorDetail = `Server returned error (${response.status})`;
        }
        throw new Error(errorDetail);
      }

      const data = await response.json();

      // Display real Gemini response
      displayStory(topic, age, data);
      showInfoBanner(`Story successfully crafted for ${topic}!`);
    } catch (err) {
      showErrorBanner(err.message || "Failed to generate story. Please verify the Gemini API configuration.");
    } finally {
      // Restore submit button state
      submitBtn.disabled = false;
      submitBtn.removeAttribute("aria-busy");
      btnSpinner.classList.add("hidden");
      btnText.textContent = "Create My Story ✨";
      loadingState.classList.add("hidden");
      loadingState.setAttribute("aria-hidden", "true");
    }
  });

  /**
   * Handle "Craft Another Story" button
   */
  if (createAnotherBtn) {
    createAnotherBtn.addEventListener("click", () => {
      form.scrollIntoView({ behavior: "smooth", block: "start" });
      topicInput.focus();
    });
  }

  // Initial pedagogy update for default selected age (8)
  const defaultChecked = document.querySelector('input[name="child_age"]:checked');
  if (defaultChecked) {
    updatePedagogyGuidance(parseInt(defaultChecked.value, 10));
  }
});
