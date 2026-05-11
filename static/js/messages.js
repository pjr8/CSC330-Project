(() => {
    const shell = document.querySelector("[data-state-url]");
    const searchForm = document.querySelector("[data-search-form]");
    const searchInput = document.querySelector("#q");
    const searchHeading = document.querySelector("[data-search-heading]");
    const summary = document.querySelector("[data-chat-summary]");
    const threadList = document.querySelector("[data-thread-list]");
    const threadCount = document.querySelector("[data-thread-count]");
    const chatHeader = document.querySelector("[data-chat-header]");
    const stream = document.querySelector("[data-live-chat-url]");
    const composer = document.querySelector("[data-composer]");

    if (!shell || !searchForm || !searchInput || !threadList || !stream || !composer) {
        return;
    }

    const inboxUrl = shell.dataset.inboxUrl || "/messages";
    const stateUrl = shell.dataset.stateUrl;
    const updateUrl = stream.dataset.liveChatUrl;
    const pollIntervalMs = 3000;
    let lastSignature = messageSignature();
    let hasActiveThread = Boolean(stream.dataset.chatId);
    let stateController = null;
    let updateController = null;
    let pollTimer = null;

    searchForm.addEventListener("submit", (event) => {
        event.preventDefault();
        loadState({q: searchInput.value.trim()});
    });

    document.addEventListener("click", (event) => {
        const target =
            event.target instanceof Element ? event.target : event.target.parentElement;
        if (!target) {
            return;
        }

        const clearSearch = target.closest("[data-clear-search]");
        if (clearSearch) {
            event.preventDefault();
            searchInput.value = "";
            loadState({q: ""});
            return;
        }

        const threadLink = target.closest("[data-thread-link]");
        if (threadLink) {
            event.preventDefault();
            const href = new URL(threadLink.href);
            loadState({
                chat: threadLink.dataset.chatId || href.searchParams.get("chat") || "",
                q: href.searchParams.get("q") || searchInput.value.trim(),
            });
        }
    });

    composer.addEventListener("submit", async (event) => {
        event.preventDefault();
        const textarea = composer.querySelector("textarea[name='content']");
        if (!textarea || textarea.disabled || !textarea.value.trim()) {
            textarea?.focus();
            return;
        }

        const formData = new FormData(composer);
        formData.set("q", searchInput.value.trim());
        setComposerBusy(true);

        try {
            const response = await window.fetch(composer.action, {
                method: "POST",
                body: formData,
                headers: {
                    Accept: "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
            });
            const payload = await response.json();
            if (!response.ok || !payload.ok) {
                return;
            }

            textarea.value = "";
            renderState(payload.state);
            updateLocation(payload.state);
            stream.scrollTop = stream.scrollHeight;
        } finally {
            setComposerBusy(false);
            textarea.focus();
        }
    });

    window.addEventListener("popstate", () => {
        loadState(stateFromLocation(), {updateHistory: false});
    });

    document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
            window.clearTimeout(pollTimer);
            updateController?.abort();
            return;
        }

        schedulePoll(250);
    });

    async function loadState(params = {}, options = {}) {
        if (stateController) {
            stateController.abort();
        }

        stateController = new AbortController();
        const controller = stateController;
        const url = buildStateUrl(params);

        try {
            const response = await window.fetch(url, {
                headers: {Accept: "application/json"},
                signal: controller.signal,
            });
            const payload = await response.json();
            if (!response.ok || !payload.ok) {
                return;
            }

            renderState(payload.state);
            if (options.updateHistory !== false) {
                updateLocation(payload.state);
            }
        } catch (error) {
            if (error.name !== "AbortError") {
                throw error;
            }
        } finally {
            if (stateController === controller) {
                stateController = null;
            }
        }
    }

    function renderState(state) {
        const activeThread = state.active_thread || null;
        const messages = Array.isArray(state.messages) ? state.messages : [];
        const threads = Array.isArray(state.threads) ? state.threads : [];
        hasActiveThread = Boolean(activeThread);

        searchInput.value = state.search_query || "";
        renderSearchClear(state.search_query || "");
        renderSummary(threads.length, hasActiveThread);
        renderThreadList(threads, state.active_chat_id || "", state.search_query || "");
        renderChatHeader(activeThread);
        renderComposer(activeThread, state.search_query || "");

        stream.dataset.chatId = activeThread ? activeThread.conversation_id : "";
        renderMessages(messages, hasActiveThread);
        lastSignature = messageSignature();
        scrollToBottom();
        schedulePoll(1000);
    }

    function renderSearchClear(searchQuery) {
        if (!searchHeading) {
            return;
        }

        searchHeading.querySelector("[data-clear-search]")?.remove();
        if (!searchQuery) {
            return;
        }

        const clearLink = document.createElement("a");
        clearLink.className = "rail-action";
        clearLink.href = inboxUrl;
        clearLink.dataset.clearSearch = "";
        clearLink.textContent = "Clear";
        searchHeading.appendChild(clearLink);
    }

    function renderSummary(threadTotal, activeThreadExists) {
        if (!summary) {
            return;
        }

        const count = document.createElement("span");
        const strong = document.createElement("strong");
        strong.textContent = String(threadTotal);
        count.append(strong, ` group chat${threadTotal === 1 ? "" : "s"}`);

        const status = document.createElement("span");
        status.textContent = activeThreadExists ? "Open study group" : "No group selected";

        summary.replaceChildren(count, status);
    }

    function renderThreadList(threads, activeChatId, searchQuery) {
        if (threadCount) {
            threadCount.textContent = String(threads.length);
        }

        const heading = threadList.querySelector(".rail-heading");
        threadList.replaceChildren();
        if (heading) {
            threadList.appendChild(heading);
        }

        if (threads.length === 0) {
            const empty = document.createElement("p");
            empty.className = "empty-note";
            empty.textContent = searchQuery
                ? "No joined study groups match your search."
                : "Join a study group to see its chat here.";
            threadList.appendChild(empty);
            return;
        }

        const list = document.createElement("ul");
        list.className = "person-list";

        for (const thread of threads) {
            const item = document.createElement("li");
            const link = document.createElement("a");
            const isActive = thread.conversation_id === activeChatId;
            link.className = `person-row${isActive ? " person-row--active" : ""}`;
            link.href = chatUrl(thread.conversation_id, searchQuery);
            link.dataset.threadLink = "";
            link.dataset.chatId = thread.conversation_id || "";
            if (isActive) {
                link.setAttribute("aria-current", "page");
            }

            const avatar = document.createElement("span");
            avatar.className = "avatar";
            avatar.setAttribute("aria-hidden", "true");
            avatar.textContent = thread.initials || "SG";

            const body = document.createElement("span");
            body.className = "person-row__body";
            const title = document.createElement("strong");
            title.textContent = thread.group_title || "Study group";
            const preview = document.createElement("span");
            preview.textContent = thread.last_message || thread.group_subject || "";
            body.append(title, preview);

            link.append(avatar, body);
            if (thread.last_sent_at) {
                const timestamp = document.createElement("time");
                timestamp.dateTime = thread.last_sent_at;
                timestamp.textContent = thread.last_sent_at_label || thread.last_sent_at;
                link.appendChild(timestamp);
            }

            item.appendChild(link);
            list.appendChild(item);
        }

        threadList.appendChild(list);
    }

    function renderChatHeader(activeThread) {
        if (!chatHeader) {
            return;
        }

        chatHeader.replaceChildren();
        if (!activeThread) {
            const identity = document.createElement("div");
            identity.className = "chat-panel__identity";
            identity.append(
                eyebrow("Group chat"),
                heading("No study group selected"),
                paragraph("Your joined study groups will appear in the chat list."),
            );
            chatHeader.appendChild(identity);
            return;
        }

        const avatar = document.createElement("div");
        avatar.className = "avatar avatar--large";
        avatar.setAttribute("aria-hidden", "true");
        avatar.textContent = activeThread.initials || "SG";

        const identity = document.createElement("div");
        identity.className = "chat-panel__identity";
        const meta = paragraph(activeThread.group_subject || "");
        if (activeThread.member_count) {
            meta.appendChild(document.createTextNode(" "));
            const members = document.createElement("span");
            members.textContent = `${activeThread.member_count} member${
                activeThread.member_count === 1 ? "" : "s"
            }`;
            meta.appendChild(members);
        }

        identity.append(
            eyebrow("Group chat"),
            heading(activeThread.group_title || "Study group"),
            meta,
        );
        chatHeader.append(avatar, identity);
    }

    function renderComposer(activeThread, searchQuery) {
        const conversationInput = composer.elements.namedItem("conversation_id");
        const groupInput = composer.elements.namedItem("group_id");
        const queryInput = composer.elements.namedItem("q");
        const textarea = composer.querySelector("textarea[name='content']");
        const button = composer.querySelector("button[type='submit']");

        if (conversationInput) {
            conversationInput.value = activeThread ? activeThread.conversation_id : "";
        }
        if (groupInput) {
            groupInput.value = activeThread ? activeThread.group_id : "";
        }
        if (queryInput) {
            queryInput.value = searchQuery || "";
        }
        if (textarea) {
            textarea.disabled = !activeThread;
        }
        if (button) {
            button.disabled = !activeThread;
        }
    }

    async function fetchUpdates() {
        if (document.hidden || !stream.dataset.chatId) {
            return;
        }

        updateController?.abort();
        updateController = new AbortController();
        const controller = updateController;
        const requestedChatId = stream.dataset.chatId;
        const url = new URL(updateUrl, window.location.origin);
        url.searchParams.set("chat", requestedChatId);

        try {
            const response = await window.fetch(url, {
                headers: {Accept: "application/json"},
                signal: controller.signal,
            });
            if (!response.ok || requestedChatId !== stream.dataset.chatId) {
                schedulePoll();
                return;
            }

            const payload = await response.json();
            const messages = Array.isArray(payload.messages) ? payload.messages : [];
            const nextSignature = messages
                .map((message) => `${message.id || ""}:${message.sent_at || ""}`)
                .join("|");

            if (nextSignature !== lastSignature) {
                const wasNearBottom = isNearBottom();
                const previousScrollTop = stream.scrollTop;
                renderMessages(messages, hasActiveThread);
                lastSignature = nextSignature;
                stream.scrollTop = wasNearBottom ? stream.scrollHeight : previousScrollTop;
            }
        } catch (error) {
            if (error.name !== "AbortError") {
                schedulePoll();
                return;
            }
        } finally {
            if (updateController === controller) {
                updateController = null;
            }
        }

        schedulePoll();
    }

    function renderMessages(messages, activeThreadExists) {
        stream.replaceChildren();

        if (messages.length === 0) {
            stream.appendChild(emptyState(activeThreadExists));
            return;
        }

        const marker = document.createElement("div");
        marker.className = "message-stream__marker";
        marker.setAttribute("aria-hidden", "true");

        const markerText = document.createElement("span");
        markerText.textContent = "Group chat";
        marker.appendChild(markerText);
        stream.appendChild(marker);

        for (const message of messages) {
            stream.appendChild(messageBubble(message));
        }
    }

    function messageBubble(message) {
        const bubble = document.createElement("article");
        bubble.className = `message-bubble ${
            message.is_mine ? "message-bubble--mine" : "message-bubble--theirs"
        }`;
        bubble.dataset.messageId = message.id || "";
        bubble.dataset.messageSentAt = message.sent_at || "";

        if (!message.is_mine) {
            const sender = document.createElement("p");
            sender.className = "message-bubble__sender";
            sender.textContent = message.sender_name || "Student";
            bubble.appendChild(sender);
        }

        const content = document.createElement("p");
        content.textContent = message.content || "";
        bubble.appendChild(content);

        if (message.sent_at) {
            const timestamp = document.createElement("time");
            timestamp.dateTime = message.sent_at;
            timestamp.textContent = message.sent_at_label || message.sent_at;
            bubble.appendChild(timestamp);
        }

        return bubble;
    }

    function emptyState(activeThreadExists) {
        const wrapper = document.createElement("div");
        wrapper.className = "empty-state";

        if (activeThreadExists) {
            wrapper.append(
                eyebrow("Ready"),
                subheading("Start the group chat"),
                paragraph("Messages sent here are visible to current group members."),
            );
            return wrapper;
        }

        wrapper.append(
            eyebrow("Groups"),
            subheading("No chat selected"),
            paragraph("Select a study group chat from the list."),
        );
        return wrapper;
    }

    function buildStateUrl(params) {
        const url = new URL(stateUrl, window.location.origin);
        const query = params.q ?? searchInput.value.trim();
        const chat = params.chat ?? "";
        const group = params.group ?? "";

        if (query) {
            url.searchParams.set("q", query);
        }
        if (chat) {
            url.searchParams.set("chat", chat);
        }
        if (group) {
            url.searchParams.set("group", group);
        }

        return url;
    }

    function updateLocation(state) {
        const url = new URL(inboxUrl, window.location.origin);
        if (state.search_query) {
            url.searchParams.set("q", state.search_query);
        }
        if (state.active_chat_id) {
            url.searchParams.set("chat", state.active_chat_id);
        }

        const nextPath = `${url.pathname}${url.search}`;
        const currentPath = `${window.location.pathname}${window.location.search}`;
        if (nextPath !== currentPath) {
            window.history.pushState({}, "", nextPath);
        }
    }

    function stateFromLocation() {
        const url = new URL(window.location.href);
        return {
            chat: url.searchParams.get("chat") || "",
            group: url.searchParams.get("group") || "",
            q: url.searchParams.get("q") || "",
        };
    }

    function chatUrl(chatId, searchQuery) {
        const url = new URL(inboxUrl, window.location.origin);
        if (chatId) {
            url.searchParams.set("chat", chatId);
        }
        if (searchQuery) {
            url.searchParams.set("q", searchQuery);
        }
        return `${url.pathname}${url.search}`;
    }

    function setComposerBusy(isBusy) {
        const button = composer.querySelector("button[type='submit']");
        const textarea = composer.querySelector("textarea[name='content']");
        if (button) {
            button.disabled = isBusy || !composer.elements.namedItem("conversation_id")?.value;
        }
        if (textarea) {
            textarea.readOnly = isBusy;
        }
    }

    function schedulePoll(delay = pollIntervalMs) {
        window.clearTimeout(pollTimer);
        pollTimer = window.setTimeout(fetchUpdates, delay);
    }

    function messageSignature() {
        return Array.from(stream.querySelectorAll("[data-message-id]"))
            .map((message) => {
                return `${message.dataset.messageId || ""}:${
                    message.dataset.messageSentAt || ""
                }`;
            })
            .join("|");
    }

    function isNearBottom() {
        const distanceFromBottom =
            stream.scrollHeight - stream.scrollTop - stream.clientHeight;
        return distanceFromBottom < 96;
    }

    function scrollToBottom() {
        window.requestAnimationFrame(() => {
            stream.scrollTop = stream.scrollHeight;
        });
    }

    function eyebrow(text) {
        const element = document.createElement("p");
        element.className = "eyebrow";
        element.textContent = text;
        return element;
    }

    function heading(text) {
        const element = document.createElement("h2");
        element.textContent = text;
        return element;
    }

    function subheading(text) {
        const element = document.createElement("h3");
        element.textContent = text;
        return element;
    }

    function paragraph(text) {
        const element = document.createElement("p");
        element.textContent = text;
        return element;
    }

    scrollToBottom();
    schedulePoll(1000);
})();
