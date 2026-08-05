const elements = {
    form: document.querySelector("#search-form"),
    question: document.querySelector("#question"),
    searchButton: document.querySelector("#search-button"),
    suggestions: document.querySelector("#suggestions"),
    systemStatus: document.querySelector("#system-status"),
    loading: document.querySelector("#loading-state"),
    error: document.querySelector("#error-state"),
    errorMessage: document.querySelector("#error-message"),
    clarification: document.querySelector("#clarification-state"),
    clarificationMessage: document.querySelector("#clarification-message"),
    clarificationOptions: document.querySelector("#clarification-options"),
    answerPanel: document.querySelector("#answer-panel"),
    answerDomain: document.querySelector("#answer-domain"),
    confidenceBadge: document.querySelector("#confidence-badge"),
    directAnswer: document.querySelector("#direct-answer"),
    explanation: document.querySelector("#explanation"),
    evidenceSection: document.querySelector("#evidence-section"),
    evidenceGrid: document.querySelector("#evidence-grid"),
    limitationsSection: document.querySelector("#limitations-section"),
    limitations: document.querySelector("#limitations"),
    sourcesSection: document.querySelector("#sources-section"),
    sources: document.querySelector("#sources"),
    capabilitiesButton: document.querySelector("#capabilities-button"),
    capabilitiesModal: document.querySelector("#capabilities-modal"),
    capabilitiesList: document.querySelector("#capabilities-list"),
    closeCapabilities: document.querySelector("#close-capabilities"),
};


function setHidden(element, hidden) {
    element.classList.toggle("hidden", hidden);
}


function resetResults() {
    setHidden(elements.error, true);
    setHidden(elements.clarification, true);
    setHidden(elements.answerPanel, true);
    elements.errorMessage.textContent = "";
    elements.clarificationOptions.replaceChildren();
}


function setLoading(loading) {
    setHidden(elements.loading, !loading);
    elements.searchButton.disabled = loading;
    elements.searchButton.textContent = loading ? "Searching?" : "Search";
}


function humanize(value) {
    return String(value ?? "")
        .replaceAll("_", " ")
        .replace(/\b\w/g, character => character.toUpperCase());
}


function formatEvidenceValue(value) {
    if (value === null || value === undefined) {
        return "Not available";
    }

    if (typeof value === "number") {
        return new Intl.NumberFormat(
            undefined,
            { maximumFractionDigits: 2 },
        ).format(value);
    }

    if (typeof value === "boolean") {
        return value ? "Yes" : "No";
    }

    return String(value);
}


function renderEvidence(evidence) {
    elements.evidenceGrid.replaceChildren();

    const entries = Object.entries(evidence || {}).filter(
        ([, value]) => value !== null && value !== undefined,
    );

    setHidden(elements.evidenceSection, entries.length === 0);

    for (const [key, value] of entries) {
        const card = document.createElement("div");
        card.className = "evidence-card";

        const label = document.createElement("div");
        label.className = "evidence-label";
        label.textContent = humanize(key);

        const valueElement = document.createElement("div");
        valueElement.className = "evidence-value";
        valueElement.textContent = formatEvidenceValue(value);

        card.append(label, valueElement);
        elements.evidenceGrid.append(card);
    }
}


function renderSources(sources) {
    elements.sources.replaceChildren();

    setHidden(elements.sourcesSection, !sources?.length);

    for (const source of sources || []) {
        const card = document.createElement("a");
        card.className = "source-card";
        card.href = source.url;
        card.target = "_blank";
        card.rel = "noopener noreferrer";

        const information = document.createElement("div");

        const provider = document.createElement("div");
        provider.className = "source-provider";
        provider.textContent = source.provider;

        const title = document.createElement("div");
        title.className = "source-title";
        title.textContent = source.title;

        const metadata = document.createElement("div");
        metadata.className = "source-meta";
        metadata.textContent = [
            source.primary ? "Primary source" : "Supporting source",
            humanize(source.role),
        ].join(" ? ");

        const arrow = document.createElement("span");
        arrow.textContent = "?";
        arrow.setAttribute("aria-hidden", "true");

        information.append(provider, title, metadata);
        card.append(information, arrow);
        elements.sources.append(card);
    }
}


function renderLimitations(limitations) {
    elements.limitations.replaceChildren();

    setHidden(
        elements.limitationsSection,
        !limitations?.length,
    );

    for (const limitation of limitations || []) {
        const item = document.createElement("li");
        item.textContent = limitation;
        elements.limitations.append(item);
    }
}


function renderClarification(payload) {
    setHidden(elements.clarification, false);
    elements.clarificationMessage.textContent = payload.answer;

    for (const option of payload.clarification_options || []) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = option;

        button.addEventListener("click", () => {
            elements.question.value = `${elements.question.value.trim()} ${option}`;
            elements.form.requestSubmit();
        });

        elements.clarificationOptions.append(button);
    }
}


function renderAnswer(payload) {
    elements.answerDomain.textContent = humanize(payload.domain);

    elements.confidenceBadge.textContent =
        `${humanize(payload.confidence)} confidence`;

    elements.confidenceBadge.className =
        `confidence-badge ${payload.confidence}`;

    elements.directAnswer.textContent = payload.answer;
    elements.explanation.textContent = payload.explanation;

    renderEvidence(payload.evidence);
    renderSources(payload.sources);
    renderLimitations(payload.limitations);

    setHidden(elements.answerPanel, false);

    elements.answerPanel.scrollIntoView({
        behavior: "smooth",
        block: "start",
    });
}


async function search(question) {
    resetResults();
    setLoading(true);

    try {
        const response = await fetch("/api/search", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                question,
                allow_web_fallback: true,
            }),
        });

        const payload = await response.json();

        if (!response.ok) {
            const detail = payload.detail || {};
            throw new Error(
                detail.message
                || detail.code
                || `Search failed with HTTP ${response.status}.`,
            );
        }

        if (payload.status === "needs_clarification") {
            renderClarification(payload);
            return;
        }

        renderAnswer(payload);

    } catch (error) {
        elements.errorMessage.textContent =
            error instanceof Error
                ? error.message
                : "An unexpected search error occurred.";

        setHidden(elements.error, false);

    } finally {
        setLoading(false);
    }
}


async function loadStatus() {
    try {
        const response = await fetch("/api/status");

        if (!response.ok) {
            throw new Error("Status request failed.");
        }

        const status = await response.json();

        const messages = [
            status.universal_orchestrator
                ? "Research engine online"
                : "Research engine unavailable",
            status.eia_cache_available
                ? "EIA operating data ready"
                : "EIA cache unavailable",
        ];

        elements.systemStatus.textContent = messages.join(" ? ");

        elements.systemStatus.classList.add(
            status.universal_orchestrator
                ? "ok"
                : "warning",
        );

    } catch {
        elements.systemStatus.textContent =
            "Live status is temporarily unavailable.";

        elements.systemStatus.classList.add("warning");
    }
}


async function loadCapabilities() {
    elements.capabilitiesList.replaceChildren();

    try {
        const response = await fetch("/api/capabilities");

        if (!response.ok) {
            throw new Error("Capabilities request failed.");
        }

        const capabilities = await response.json();

        for (const capability of capabilities) {
            const card = document.createElement("article");
            card.className = "capability-card";

            const title = document.createElement("h3");
            title.textContent = capability.capability;

            const metadata = document.createElement("div");
            metadata.className = "capability-meta";
            metadata.textContent =
                `${humanize(capability.status)} ? ${capability.controlling_source}`;

            const examples = document.createElement("p");
            examples.textContent =
                capability.examples.join(" ? ");

            card.append(title, metadata, examples);
            elements.capabilitiesList.append(card);
        }

    } catch (error) {
        const message = document.createElement("p");
        message.textContent =
            error instanceof Error
                ? error.message
                : "Capabilities could not be loaded.";

        elements.capabilitiesList.append(message);
    }
}


elements.form.addEventListener("submit", event => {
    event.preventDefault();

    const question = elements.question.value.trim();

    if (question.length < 2) {
        elements.errorMessage.textContent =
            "Enter a complete energy-market question.";

        setHidden(elements.error, false);
        return;
    }

    search(question);
});


elements.question.addEventListener("input", () => {
    elements.question.style.height = "auto";
    elements.question.style.height =
        `${Math.min(elements.question.scrollHeight, 160)}px`;
});


elements.question.addEventListener("keydown", event => {
    if (
        event.key === "Enter"
        && !event.shiftKey
    ) {
        event.preventDefault();
        elements.form.requestSubmit();
    }
});


elements.suggestions.addEventListener("click", event => {
    const button = event.target.closest("button");

    if (!button) {
        return;
    }

    elements.question.value = button.textContent.trim();
    elements.form.requestSubmit();
});


elements.capabilitiesButton.addEventListener("click", async () => {
    setHidden(elements.capabilitiesModal, false);
    await loadCapabilities();
});


elements.closeCapabilities.addEventListener("click", () => {
    setHidden(elements.capabilitiesModal, true);
});


elements.capabilitiesModal.addEventListener("click", event => {
    if (event.target.classList.contains("modal-backdrop")) {
        setHidden(elements.capabilitiesModal, true);
    }
});


document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
        setHidden(elements.capabilitiesModal, true);
    }
});


loadStatus();
