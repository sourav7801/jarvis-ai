const TOKEN =
    window.JARVIS_TOKEN;


let zIndex =
    100;

let selectedTimeframe =
    "15m";

let chartSlots = [
    {
        symbol:
            "NIFTY",

        timeframe:
            "15m"
    }
];

let recognition =
    null;

let speakAnswers =
    false;

let lastRoute =
    "MASTER";


let commandInFlight =
    false;

let commandInFlightText =
    "";


async function api(
    path,
    options = {}
) {

    options.headers = {
        ...(options.headers || {}),
        "X-Jarvis-Token":
            TOKEN,
        "Content-Type":
            "application/json"
    };


    const response =
        await fetch(
            path,
            options
        );


    const value =
        await response.json();


    if (!response.ok) {

        throw new Error(
            value.error
            || value.response
            || "JARVIS API error"
        );
    }


    return value;
}


function setCoreState(
    state
) {

    document.body.dataset.coreState =
        state;


    const coreText =
        document.getElementById(
            "coreText"
        );


    const masterState =
        document.getElementById(
            "masterState"
        );


    const labels = {
        ready:
            "ONLINE",

        listening:
            "LISTENING",

        thinking:
            "THINKING",

        approval:
            "APPROVAL",

        error:
            "ERROR",

        complete:
            "COMPLETE"
    };


    coreText.textContent =
        labels[state]
        || state.toUpperCase();


    masterState.textContent =
        labels[state]
        || state.toUpperCase();
}


function addConversation(
    who,
    text,
    route = null
) {

    const holder =
        document.getElementById(
            "conversation"
        );


    const item =
        document.createElement(
            "div"
        );


    item.className =
        "conversationItem "
        + (
            who === "YOU"
            ? "you"
            : "jarvis"
        );


    const speaker =
        document.createElement(
            "div"
        );


    speaker.className =
        "speaker";

    speaker.textContent =
        who;


    const message =
        document.createElement(
            "div"
        );


    message.className =
        "message";


    if (
        who === "JARVIS"
        && route
    ) {

        const card =
            document.createElement(
                "div"
            );


        card.className =
            "resultCard";


        const meta =
            document.createElement(
                "div"
            );


        meta.className =
            "resultMeta";

        meta.textContent =
            route
            + " · "
            + new Date()
                .toLocaleTimeString();


        const body =
            document.createElement(
                "div"
            );


        body.className =
            "resultBody";

        body.textContent =
            text;


        card.append(
            meta,
            body
        );


        message.appendChild(
            card
        );


    } else {

        message.textContent =
            text;
    }


    item.append(
        speaker,
        message
    );


    holder.appendChild(
        item
    );


    holder.scrollTop =
        holder.scrollHeight;
}


function focusWindow(
    win
) {

    zIndex++;


    document
        .querySelectorAll(
            ".jarvisWindow"
        )
        .forEach(
            item =>
                item.classList
                    .remove(
                        "focused"
                    )
        );


    win.style.zIndex =
        String(
            zIndex
        );


    win.classList.add(
        "focused"
    );
}


function openWindow(
    name
) {

    const win =
        document.getElementById(
            "win-" + name
        );


    if (!win) return;


    win.style.display =
        "block";


    win.classList.remove(
        "minimized"
    );


    focusWindow(
        win
    );


    persistWorkspace();
}


function closeWindow(
    name
) {

    if (
        name === "core"
    ) {
        return;
    }


    const win =
        document.getElementById(
            "win-" + name
        );


    if (!win) return;


    win.style.display =
        "none";


    persistWorkspace();
}


function maximizeWindow(
    name
) {

    const win =
        document.getElementById(
            "win-" + name
        );


    if (!win) return;


    openWindow(
        name
    );


    win.classList.add(
        "maximized"
    );


    focusWindow(
        win
    );
}


function closeAllWindows() {

    document
        .querySelectorAll(
            ".jarvisWindow"
        )
        .forEach(
            win => {

                if (
                    win.dataset.window
                    !== "core"
                ) {

                    win.style.display =
                        "none";
                }
            }
        );


    openWindow(
        "core"
    );
}


function resetWindowClasses() {

    document
        .querySelectorAll(
            ".jarvisWindow"
        )
        .forEach(
            win => {

                win.classList.remove(
                    "maximized",
                    "minimized"
                );
            }
        );
}


function setGeometry(
    name,
    left,
    top,
    width,
    height
) {

    const win =
        document.getElementById(
            "win-" + name
        );


    if (!win) return;


    win.style.display =
        "block";

    win.style.left =
        left;

    win.style.top =
        top;

    win.style.width =
        width;

    win.style.height =
        height;
}


function applyLayout(
    name
) {

    resetWindowClasses();


    if (
        name === "command"
    ) {

        /*
         * JARVIS V6 SIMPLE HOME
         * One primary intelligence surface.
         * Specialist workspaces open only when requested.
         */
        closeAllWindows();

        setGeometry(
            "core",
            "10%",
            "5%",
            "80%",
            "90%"
        );

        closeWindow("chart");
        closeWindow("quant");
        closeWindow("research");
        closeWindow("missions");
        closeWindow("paper");
        closeWindow("system");
        closeWindow("evidence");
        closeWindow("apps");
    }


    if (
        name === "trading"
    ) {

        setGeometry(
            "chart",
            "1%",
            "2%",
            "55%",
            "62%"
        );

        setGeometry(
            "quant",
            "57%",
            "2%",
            "42%",
            "46%"
        );

        setGeometry(
            "paper",
            "1%",
            "66%",
            "55%",
            "32%"
        );

        setGeometry(
            "missions",
            "57%",
            "50%",
            "42%",
            "48%"
        );


        closeWindow(
            "core"
        );

        closeWindow(
            "research"
        );

        closeWindow(
            "system"
        );

        closeWindow(
            "evidence"
        );

        closeWindow(
            "apps"
        );
    }


    if (
        name === "research"
    ) {

        setGeometry(
            "research",
            "1%",
            "2%",
            "54%",
            "96%"
        );

        setGeometry(
            "chart",
            "56%",
            "2%",
            "43%",
            "55%"
        );

        setGeometry(
            "missions",
            "56%",
            "59%",
            "43%",
            "39%"
        );


        closeWindow(
            "core"
        );

        closeWindow(
            "quant"
        );

        closeWindow(
            "paper"
        );

        closeWindow(
            "apps"
        );

        closeWindow(
            "system"
        );

        closeWindow(
            "evidence"
        );
    }


    if (
        name === "mission"
    ) {

        setGeometry(
            "core",
            "1%",
            "2%",
            "42%",
            "96%"
        );

        setGeometry(
            "missions",
            "44%",
            "2%",
            "55%",
            "48%"
        );

        setGeometry(
            "evidence",
            "44%",
            "52%",
            "55%",
            "46%"
        );


        closeWindow(
            "chart"
        );

        closeWindow(
            "quant"
        );

        closeWindow(
            "paper"
        );

        closeWindow(
            "research"
        );

        closeWindow(
            "apps"
        );

        closeWindow(
            "system"
        );
    }


    persistWorkspace();
}


function persistWorkspace() {

    const state = {};


    document
        .querySelectorAll(
            ".jarvisWindow"
        )
        .forEach(
            win => {

                state[
                    win.dataset.window
                ] = {
                    display:
                        win.style.display,

                    left:
                        win.style.left,

                    top:
                        win.style.top,

                    width:
                        win.style.width,

                    height:
                        win.style.height,

                    minimized:
                        win.classList
                            .contains(
                                "minimized"
                            ),

                    maximized:
                        win.classList
                            .contains(
                                "maximized"
                            )
                };
            }
        );


    state.chartSlots =
        chartSlots;


    localStorage.setItem(
        "jarvisV6Workspace",
        JSON.stringify(
            state
        )
    );
}


function restoreWorkspace() {

    try {

        const state =
            JSON.parse(
                localStorage.getItem(
                    "jarvisV6Workspace"
                )
            );


        if (!state) {

            applyLayout(
                "command"
            );

            return;
        }


        for (
            const [
                name,
                value
            ]
            of Object.entries(
                state
            )
        ) {

            if (
                name === "chartSlots"
            ) {
                continue;
            }


            const win =
                document.getElementById(
                    "win-" + name
                );


            if (!win) continue;


            for (
                const property
                of (
                    "display",
                    "left",
                    "top",
                    "width",
                    "height"
                )
            ) {

                if (
                    value[property]
                ) {

                    win.style[
                        property
                    ] =
                        value[
                            property
                        ];
                }
            }


            if (
                value.minimized
            ) {

                win.classList.add(
                    "minimized"
                );
            }


            if (
                value.maximized
            ) {

                win.classList.add(
                    "maximized"
                );
            }
        }


        if (
            Array.isArray(
                state.chartSlots
            )
        ) {

            chartSlots =
                state.chartSlots;
        }


    } catch (_) {

        applyLayout(
            "command"
        );
    }
}


function makeDraggable(
    win
) {

    const header =
        win.querySelector(
            ".windowHeader"
        );


    let dragging =
        false;

    let originX =
        0;

    let originY =
        0;

    let startLeft =
        0;

    let startTop =
        0;


    header.addEventListener(
        "mousedown",
        event => {

            if (
                event.target.tagName
                === "BUTTON"
            ) {

                return;
            }


            if (
                win.classList
                    .contains(
                        "maximized"
                    )
            ) {

                return;
            }


            dragging =
                true;


            originX =
                event.clientX;

            originY =
                event.clientY;


            startLeft =
                win.offsetLeft;

            startTop =
                win.offsetTop;


            focusWindow(
                win
            );


            event.preventDefault();
        }
    );


    window.addEventListener(
        "mousemove",
        event => {

            if (!dragging)
                return;


            const desktop =
                document.getElementById(
                    "desktop"
                );


            let x =
                startLeft
                + event.clientX
                - originX;


            let y =
                startTop
                + event.clientY
                - originY;


            x =
                Math.max(
                    0,
                    Math.min(
                        x,
                        desktop.clientWidth
                        - 80
                    )
                );


            y =
                Math.max(
                    0,
                    Math.min(
                        y,
                        desktop.clientHeight
                        - 35
                    )
                );


            win.style.left =
                x + "px";

            win.style.top =
                y + "px";
        }
    );


    window.addEventListener(
        "mouseup",
        () => {

            if (!dragging)
                return;


            dragging =
                false;


            snapWindow(
                win
            );


            persistWorkspace();
        }
    );


    win.addEventListener(
        "mousedown",
        () =>
            focusWindow(
                win
            )
    );
}


function snapWindow(
    win
) {

    const desktop =
        document.getElementById(
            "desktop"
        );


    const margin =
        35;


    const left =
        win.offsetLeft;

    const top =
        win.offsetTop;


    const right =
        desktop.clientWidth
        - (
            win.offsetLeft
            + win.offsetWidth
        );


    if (
        left < margin
    ) {

        win.style.left =
            "0px";

        win.style.top =
            "0px";

        win.style.width =
            "50%";

        win.style.height =
            "100%";

        return;
    }


    if (
        right < margin
    ) {

        win.style.left =
            "50%";

        win.style.top =
            "0px";

        win.style.width =
            "50%";

        win.style.height =
            "100%";

        return;
    }


    if (
        top < margin
    ) {

        win.style.left =
            "0px";

        win.style.top =
            "0px";

        win.style.width =
            "100%";

        win.style.height =
            "50%";
    }
}


function executeWorkspaceActions(
    actions
) {

    for (
        const action
        of (
            actions || []
        )
    ) {

        if (
            action.type
            === "open_window"
        ) {

            openWindow(
                action.window
            );
        }


        if (
            action.type
            === "close_window"
        ) {

            closeWindow(
                action.window
            );
        }


        if (
            action.type
            === "maximize_window"
        ) {

            maximizeWindow(
                action.window
            );
        }


        if (
            action.type
            === "layout"
        ) {

            applyLayout(
                action.layout
            );
        }


        if (
            action.type
            === "close_all"
        ) {

            closeAllWindows();
        }


        if (
            action.type
            === "save_workspace"
        ) {

            persistWorkspace();
        }


        if (
            action.type
            === "restore_workspace"
        ) {

            restoreWorkspace();
        }


        if (
            action.type
            === "chart_symbol"
        ) {

            const index =
                Math.max(
                    0,
                    Math.min(
                        3,
                        Number(
                            action.slot
                        )
                    )
                );


            chartSlots[index] = {
                symbol:
                    action.symbol,

                timeframe:
                    action.timeframe
                    || "15m"
            };


            if (index === 0) {

                const selector =
                    document.getElementById(
                        "chartSymbol"
                    );


                if (selector) {

                    selector.value =
                        action.symbol;
                }


                selectedTimeframe =
                    action.timeframe
                    || "15m";


                document
                    .querySelectorAll(
                        "[data-timeframe]"
                    )
                    .forEach(
                        button => {

                            button.classList.toggle(
                                "selected",
                                button.dataset.timeframe
                                === selectedTimeframe
                            );
                        }
                    );
            }


            renderChartSlots();
        }


        if (
            action.type
            === "chart_layout"
        ) {

            setChartCount(
                Number(
                    action.count
                )
            );
        }
    }
}


async function executeCommand(
    forced = null,
    metadata = {}
) {

    const input =
        document.getElementById(
            "commandInput"
        );


    const text =
        (
            forced
            ?? input.value
        ).trim();


    if (!text)
        return;


    if (commandInFlight) {

        const normalized =
            text
            .toLowerCase()
            .replace(
                /\s+/g,
                " "
            )
            .trim();


        const active =
            commandInFlightText
            .toLowerCase()
            .replace(
                /\s+/g,
                " "
            )
            .trim();


        if (
            normalized === active
        ) {

            return;
        }


        addConversation(
            "JARVIS",
            "I'm finishing the current request first.",
            "BUSY"
        );


        return;
    }


    commandInFlight =
        true;


    commandInFlightText =
        text;


    input.value = "";


    addConversation(
        "YOU",
        text
    );


    document.getElementById(
        "coreMission"
    ).textContent =
        text;


    document.getElementById(
        "readyState"
    ).textContent =
        "THINKING";


    setCoreState(
        "thinking"
    );


    try {

        const result =
            await api(
                "/api/command",
                {
                    method:
                        "POST",

                    body:
                        JSON.stringify(
                            {
                                text,

                                input_mode:
                                    metadata.inputMode
                                    || "typed",

                                speech_confidence:
                                    Number.isFinite(
                                        Number(metadata.speechConfidence)
                                    )
                                    ? Number(metadata.speechConfidence)
                                    : null
                            }
                        )
                }
            );


        lastRoute =
            result.route
            || "MASTER";


        document.getElementById(
            "activeRoute"
        ).textContent =
            lastRoute;


        addConversation(
            "JARVIS",
            result.response
            || "Completed.",
            lastRoute
        );


        renderSpecialistResult(
            result
        );


        executeWorkspaceActions(
            result.workspace_actions
        );


        setCoreState(
            "complete"
        );


        setTimeout(
            () =>
                setCoreState(
                    "ready"
                ),
            900
        );


    } catch (error) {

        addConversation(
            "JARVIS",
            error.message,
            "ERROR"
        );


        setCoreState(
            "error"
        );


    } finally {

        commandInFlight =
            false;


        commandInFlightText =
            "";
    }


    document.getElementById(
        "readyState"
    ).textContent =
        "READY";


    refreshEvidence();
}


function specialistTargetForRoute(
    route
) {

    const value =
        String(route || "")
        .toUpperCase();


    if (
        value.includes("WEB")
        || value.includes("RESEARCH")
        || value.includes("NEWS")
    ) {

        return {
            feed: "researchFeed",
            window: "research"
        };
    }


    if (
        value.includes("PAPER")
        || value.includes("PORTFOLIO")
        || value.includes("AUTONOM")
    ) {

        return {
            feed: "paperFeed",
            window: "paper"
        };
    }


    if (
        value.includes("COMPANY")
        || value.includes("VENTURE")
        || value.includes("BUSINESS")
    ) {

        return {
            feed: "companyFeed",
            window: "company"
        };
    }


    return null;
}


function sourceLinksFromPayload(
    payload
) {

    const links = [];
    const seen = new Set();


    const visit = value => {

        if (
            !value
            || links.length >= 12
        ) return;


        if (Array.isArray(value)) {

            value.forEach(visit);
            return;
        }


        if (typeof value !== "object")
            return;


        const url =
            value.url
            || value.link
            || value.source_url;


        if (
            typeof url === "string"
            && /^https?:\/\//i.test(url)
            && !seen.has(url)
        ) {

            seen.add(url);
            links.push({
                url,
                label:
                    String(
                        value.title
                        || value.name
                        || value.source
                        || new URL(url).hostname
                    )
            });
        }


        Object.values(value).forEach(visit);
    };


    visit(payload);
    return links;
}


function renderSpecialistResult(
    result
) {

    const target =
        specialistTargetForRoute(
            result?.route
        );


    if (!target)
        return;


    const feed =
        document.getElementById(
            target.feed
        );


    if (!feed)
        return;


    const card =
        document.createElement(
            "article"
        );

    card.className =
        "resultCard specialistResultCard";


    const meta =
        document.createElement(
            "div"
        );

    meta.className =
        "resultMeta";

    meta.textContent =
        String(result.route || "SPECIALIST")
        + " · VERIFIED RESULT · "
        + new Date().toLocaleTimeString();


    const body =
        document.createElement(
            "div"
        );

    body.className =
        "resultBody";

    body.textContent =
        String(
            result.response
            || "The specialist completed without a text summary."
        );


    card.append(
        meta,
        body
    );


    const sources =
        sourceLinksFromPayload(
            result.raw
        );


    if (sources.length) {

        const sourceHolder =
            document.createElement(
                "div"
            );

        sourceHolder.className =
            "specialistSources";


        sources.forEach(
            source => {

                const link =
                    document.createElement(
                        "a"
                    );

                link.href = source.url;
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                link.textContent = source.label;
                sourceHolder.appendChild(link);
            }
        );


        card.appendChild(
            sourceHolder
        );
    }


    feed.replaceChildren(
        card
    );


    openWindow(
        target.window
    );
}


function bindCommandButtons() {

    document
        .querySelectorAll(
            "[data-command]"
        )
        .forEach(
            button => {

                button.addEventListener(
                    "click",
                    () =>
                        executeCommand(
                            button.dataset.command
                        )
                );
            }
        );
}


function setChartCount(
    count
) {

    count =
        (
            count >= 4
            ? 4
            : (
                count >= 2
                ? 2
                : 1
            )
        );


    while (
        chartSlots.length
        < count
    ) {

        const defaults = [
            "NIFTY",
            "BANKNIFTY",
            "CRUDEOIL",
            "BTC"
        ];


        chartSlots.push(
            {
                symbol:
                    defaults[
                        chartSlots.length
                    ],

                timeframe:
                    selectedTimeframe
            }
        );
    }


    chartSlots =
        chartSlots.slice(
            0,
            count
        );


    renderChartSlots();
}


function renderChartSlots() {

    const grid =
        document.getElementById(
            "chartGrid"
        );


    grid.className = "";


    if (
        chartSlots.length === 2
    ) {

        grid.classList.add(
            "layout2"
        );
    }


    if (
        chartSlots.length === 4
    ) {

        grid.classList.add(
            "layout4"
        );
    }


    grid.innerHTML = "";


    chartSlots.forEach(
        (
            slot,
            index
        ) => {

            const pane =
                document.createElement(
                    "div"
                );


            pane.className =
                "chartPane";


            const canvas =
                document.createElement(
                    "canvas"
                );


            canvas.className =
                "chartCanvas";

            canvas.id =
                "chartCanvas"
                + index;


            const status =
                document.createElement(
                    "div"
                );


            status.className =
                "chartStatus";

            status.id =
                "chartStatus"
                + index;

            status.textContent =
                slot.symbol
                + " · "
                + slot.timeframe
                + " · LOADING";


            pane.append(
                canvas,
                status
            );


            grid.appendChild(
                pane
            );


            loadChart(
                index
            );
        }
    );


    persistWorkspace();
}


async function loadChart(
    index
) {

    const slot =
        chartSlots[
            index
        ];


    if (!slot)
        return;


    const status =
        document.getElementById(
            "chartStatus"
            + index
        );


    try {

        const data =
            await api(
                "/api/chart?symbol="
                + encodeURIComponent(
                    slot.symbol
                )
                + "&timeframe="
                + encodeURIComponent(
                    slot.timeframe
                )
            );


        const canvas =
            document.getElementById(
                "chartCanvas"
                + index
            );


        drawCandles(
            canvas,
            data.bars || []
        );


        status.textContent =
            slot.symbol
            + " · "
            + slot.timeframe
            + " · "
            + (
                data.verified
                ? "VERIFIED "
                + data.provider
                : (
                    "NO VERIFIED FEED · "
                    + (
                        data.error
                        || "unavailable"
                    )
                )
            );


        if (
            index === 0
        ) {

            document.getElementById(
                "chartTitle"
            ).textContent =
                slot.symbol
                + " · "
                + slot.timeframe;


            document.getElementById(
                "chartProvider"
            ).textContent =
                (
                    data.verified
                    ? "VERIFIED · "
                        + data.provider
                    : "DATA UNAVAILABLE"
                );


            const bars =
                data.bars
                || [];


            document.getElementById(
                "chartPrice"
            ).textContent =
                (
                    bars.length
                    ? Number(
                        bars[
                            bars.length - 1
                        ].close
                    ).toLocaleString()
                    : "—"
                );
        }


    } catch (error) {

        if (status) {

            status.textContent =
                "ERROR · "
                + error.message;
        }
    }
}


function drawCandles(
    canvas,
    bars
) {

    const ratio =
        window.devicePixelRatio
        || 1;


    const rect =
        canvas.getBoundingClientRect();


    canvas.width =
        Math.max(
            1,
            rect.width
            * ratio
        );


    canvas.height =
        Math.max(
            1,
            rect.height
            * ratio
        );


    const ctx =
        canvas.getContext(
            "2d"
        );


    ctx.setTransform(
        ratio,
        0,
        0,
        ratio,
        0,
        0
    );


    const width =
        rect.width;

    const height =
        rect.height;


    ctx.clearRect(
        0,
        0,
        width,
        height
    );


    ctx.strokeStyle =
        "rgba(73,177,216,.08)";


    for (
        let i = 1;
        i < 6;
        i++
    ) {

        const y =
            height
            * i
            / 6;


        ctx.beginPath();

        ctx.moveTo(
            0,
            y
        );

        ctx.lineTo(
            width,
            y
        );

        ctx.stroke();
    }


    if (
        !bars
        || bars.length < 2
    ) {

        ctx.fillStyle =
            "#597788";

        ctx.font =
            "12px Segoe UI";

        ctx.textAlign =
            "center";


        ctx.fillText(
            "NO VERIFIED CANDLE DATA",
            width / 2,
            height / 2
        );


        return;
    }


    const values = [];


    for (
        const bar
        of bars
    ) {

        values.push(
            bar.high,
            bar.low
        );
    }


    const high =
        Math.max(
            ...values
        );


    const low =
        Math.min(
            ...values
        );


    const range =
        Math.max(
            high - low,
            .000001
        );


    const pad =
        12;


    const usableHeight =
        height
        - pad * 2;


    const step =
        width
        / bars.length;


    const candleWidth =
        Math.max(
            2,
            Math.min(
                8,
                step * .62
            )
        );


    function y(
        value
    ) {

        return pad
        + (
            high - value
        )
        / range
        * usableHeight;
    }


    bars.forEach(
        (
            bar,
            index
        ) => {

            const x =
                index * step
                + step / 2;


            const rising =
                bar.close
                >= bar.open;


            const color =
                (
                    rising
                    ? "#65f2a8"
                    : "#ff6475"
                );


            ctx.strokeStyle =
                color;

            ctx.fillStyle =
                color;


            ctx.beginPath();

            ctx.moveTo(
                x,
                y(
                    bar.high
                )
            );

            ctx.lineTo(
                x,
                y(
                    bar.low
                )
            );

            ctx.stroke();


            const top =
                Math.min(
                    y(
                        bar.open
                    ),
                    y(
                        bar.close
                    )
                );


            const bottom =
                Math.max(
                    y(
                        bar.open
                    ),
                    y(
                        bar.close
                    )
                );


            ctx.fillRect(
                x
                - candleWidth / 2,
                top,
                candleWidth,
                Math.max(
                    1,
                    bottom - top
                )
            );
        }
    );
}


async function refreshStatus() {

    try {

        const value =
            await api(
                "/api/status"
            );


        const agents =
            value.agents
            || [];


        document.getElementById(
            "agentCount"
        ).textContent =
            (
                value.agent_health
                || agents
            ).length;


        renderAgentMesh(
            value.agent_health
            || agents
        );


        renderSystem(
            value
        );


        document.getElementById(
            "readyState"
        ).textContent =
            (
                value.protected_core
                ? "READY"
                : "DEGRADED"
            );


    } catch (_) {

        document.getElementById(
            "readyState"
        ).textContent =
            "DEGRADED";
    }
}


function renderAgentMesh(
    agents
) {

    const holder =
        document.getElementById(
            "agentMesh"
        );


    holder.innerHTML = "";


    for (
        const name
        of agents
    ) {

        const card =
            document.createElement(
                "div"
            );


        const record =
            typeof name === "string"
            ? {
                name,
                status: "REGISTERED",
                detail: "Registered entrypoint; health detail unavailable."
            }
            : name;


        card.className =
            "agentCard "
            + String(
                record.status
                || "degraded"
            ).toLowerCase();

        card.textContent =
            String(
                record.name
            ).toUpperCase();


        card.title =
            String(
                record.status
                || "UNKNOWN"
            )
            + " · "
            + String(
                record.detail
                || "No readiness detail."
            );


        holder.appendChild(
            card
        );
    }
}


function renderSystem(
    value
) {

    const holder =
        document.getElementById(
            "systemGrid"
        );


    holder.innerHTML = "";


    const cards = [
        [
            "PROTECTED CORE",
            value.protected_core
            ? "PASS"
            : "FAULT"
        ],

        [
            "AGENTS",
            (
                value.agents
                || []
            ).length
        ]
    ];


    for (
        const [
            name,
            component
        ]
        of Object.entries(
            value.components
            || {}
        )
    ) {

        cards.push(
            [
                name
                    .replace(
                        "jarvis_",
                        ""
                    )
                    .replace(
                        "_status",
                        ""
                    )
                    .toUpperCase(),

                (
                    component
                    && !component.error
                    ? "READY"
                    : "DEGRADED"
                )
            ]
        );
    }


    for (
        const [
            label,
            status
        ]
        of cards
    ) {

        const card =
            document.createElement(
                "div"
            );


        card.className =
            "systemCard";


        const span =
            document.createElement(
                "span"
            );

        span.textContent =
            label;


        const b =
            document.createElement(
                "b"
            );

        b.textContent =
            status;


        card.append(
            span,
            b
        );


        holder.appendChild(
            card
        );
    }
}


async function refreshMarket() {

    try {

        const data =
            await api(
                "/api/market"
            );


        const latest =
            data.latest
            || {};


        document.getElementById(
            "metricSpot"
        ).textContent =
            latest.spot
            ?? "—";


        document.getElementById(
            "metricIV"
        ).textContent =
            latest.atm_iv
            ?? "—";


        document.getElementById(
            "metricPCR"
        ).textContent =
            latest.pcr_oi
            ?? "—";


        document.getElementById(
            "metricHistory"
        ).textContent =
            data.history_count
            ?? 0;


    } catch (_) {}
}


function paperMoney(value) {
    const number = Number(value || 0);
    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 2
    }).format(number);
}


function paperTradeRow(item, closed = false) {
    const row = document.createElement("div");
    row.className = "paperTradeRow";
    const pnl = Number(closed ? item.realized_pnl : item.unrealized_pnl || 0);
    const values = [
        `${item.symbol || "—"} · ${item.side || "—"}`,
        `QTY ${Number(item.quantity || 0).toLocaleString("en-IN")}`,
        `ENTRY ${Number(item.entry || 0).toLocaleString("en-IN")}`,
        closed
            ? `EXIT ${Number(item.exit_price || 0).toLocaleString("en-IN")}`
            : `SL ${Number(item.stop || 0).toLocaleString("en-IN")} · TP ${Number(item.target || 0).toLocaleString("en-IN")}`,
        `${pnl >= 0 ? "+" : ""}${paperMoney(pnl)}`
    ];
    values.forEach((value, index) => {
        const cell = index === 0 ? document.createElement("strong") : document.createElement("span");
        cell.textContent = value;
        if (index === 4) cell.className = pnl >= 0 ? "positive" : "negative";
        row.appendChild(cell);
    });
    row.title = [
        `Timeframe: ${item.timeframe || "—"}`,
        `Strategy: ${item.strategy || "—"}`,
        `Multiplier: ${item.contract_multiplier || 1}`,
        `Currency: ${item.native_currency || "—"} → ${item.valuation_currency || "INR"}`,
        `Costs: ${item.cost_model_status || "UNCONFIGURED"}`,
        ...(!closed ? [
            `Current mark: ${Number(item.mark || 0).toLocaleString("en-IN")}`,
            `Initial stop: ${Number(item.initial_stop || item.stop || 0).toLocaleString("en-IN")}`,
            item.exit_policy
                ? `Exit policy: breakeven ${Number(item.exit_policy.breakeven_at_r || 0).toFixed(2)}R · trail starts ${Number(item.exit_policy.trailing_at_r || 0).toFixed(2)}R · distance ${Number(item.exit_policy.trailing_distance_r || 0).toFixed(2)}R · max hold ${Number(item.exit_policy.max_hold_minutes || 0)}m`
                : "Exit policy: fixed stop and target"
        ] : [
            `Exit reason: ${item.exit_reason || item.metadata?.exit_reason || "—"}`,
            `MAE: ${paperMoney(item.mae_pnl)} · ${Number(item.mae_r || 0).toFixed(2)}R`,
            `MFE: ${paperMoney(item.mfe_pnl)} · ${Number(item.mfe_r || 0).toFixed(2)}R`
        ])
    ].join("\n");
    return row;
}


async function refreshPaperPortfolio() {
    const paperWindow = document.getElementById("win-paper");
    if (!paperWindow || paperWindow.style.display === "none") return;
    try {
        const data = await api("/api/paper-portfolio");
        const portfolio = data.portfolio || {};
        const autonomy = data.autonomy || {};
        document.getElementById("paperRunState").textContent = autonomy.running ? "AUTONOMY RUNNING" : "AUTONOMY PAUSED";
        document.getElementById("paperEquity").textContent = paperMoney(portfolio.equity);
        const totalPnl = Number(portfolio.total_pnl || 0);
        const pnlElement = document.getElementById("paperTotalPnl");
        pnlElement.textContent = `${totalPnl >= 0 ? "+" : ""}${paperMoney(totalPnl)}`;
        pnlElement.className = totalPnl >= 0 ? "positive" : "negative";
        document.getElementById("paperGross").textContent = paperMoney(portfolio.gross_exposure);
        document.getElementById("paperRisk").textContent = `${paperMoney(portfolio.risk_at_stops)} · ${Number(portfolio.risk_percent_of_equity || 0).toFixed(2)}%`;
        const dailyPnl = Number(portfolio.daily_total_pnl || 0);
        const dailyElement = document.getElementById("paperDailyPnl");
        dailyElement.textContent = `${dailyPnl >= 0 ? "+" : ""}${paperMoney(dailyPnl)} / ${paperMoney(portfolio.daily_loss_limit)}`;
        dailyElement.className = dailyPnl >= 0 ? "positive" : "negative";
        document.getElementById("paperDrawdown").textContent =
            `${paperMoney(portfolio.drawdown)} · ${Number(portfolio.drawdown_percent || 0).toFixed(2)}% / ${paperMoney(portfolio.peak_equity)}`;
        const locks = Array.isArray(portfolio.risk_locks) ? portfolio.risk_locks : [];
        const entryGate = document.getElementById("paperEntryGate");
        entryGate.textContent = locks.length ? locks.join(" · ").replaceAll("_", " ") : "OPEN · ALL DESK GATES PASS";
        entryGate.className = locks.length ? "negative" : "positive";
        document.getElementById("paperCorrelation").textContent =
            `${portfolio.correlation_clusters_status || "UNCONFIGURED"} · ${Object.keys(portfolio.correlation_cluster_exposure || {}).length} CLUSTERS`;

        const positions = Array.isArray(portfolio.positions) ? portfolio.positions : [];
        const closed = Array.isArray(data.closed_positions) ? data.closed_positions : [];
        document.getElementById("paperOpenCount").textContent = `${positions.length} OPEN`;
        document.getElementById("paperClosedCount").textContent = `${closed.length} CLOSED`;
        const openHolder = document.getElementById("paperPositions");
        const closedHolder = document.getElementById("paperClosedTrades");
        openHolder.innerHTML = "";
        closedHolder.innerHTML = "";
        if (positions.length) positions.forEach(item => openHolder.appendChild(paperTradeRow(item)));
        else openHolder.textContent = "No open paper positions.";
        if (closed.length) closed.slice(0, 30).forEach(item => closedHolder.appendChild(paperTradeRow(item, true)));
        else closedHolder.textContent = "No closed paper trades.";

        const optionDesk = data.defined_risk_option_spreads || {};
        const optionAutonomy = data.options_paper_autonomy || {};
        const optionRows = Array.isArray(optionDesk.positions) ? optionDesk.positions : [];
        const optionHolder = document.getElementById("paperOptionSpreads");
        document.getElementById("paperOptionCount").textContent = `${Number(optionDesk.open_count || 0)} OPEN`;
        optionHolder.innerHTML = "";
        if (optionRows.length) {
            optionRows.slice(0, 20).forEach(item => {
                const payload = item.payload || {};
                optionHolder.appendChild(companyRow("paperTradeRow", [
                    `${item.underlying || "—"} · ${item.strategy || "DEFINED RISK"}`,
                    `LOTS ${Number(item.quantity || 0)}`,
                    `BUY ${payload.long_symbol || "—"}`,
                    `HEDGE ${payload.short_symbol || "—"}`,
                    `MAX LOSS ${paperMoney(item.max_loss)}`
                ]));
            });
        } else {
            optionHolder.textContent = "No governed option spreads. Naked short options remain blocked.";
        }
        document.getElementById("paperOptionCount").title =
            `${Number(optionAutonomy.processed || 0)} chains processed · ${Number(optionAutonomy.opened || 0)} opened · `
            + `${Object.entries(optionAutonomy.rejections || {}).map(([key, value]) => `${key}: ${value}`).join(" · ") || "no rejection telemetry"}`;

        document.getElementById("paperLastScan").textContent = autonomy.last_scan_at
            ? `LAST SCAN ${new Date(autonomy.last_scan_at).toLocaleTimeString()}`
            : "NO COMPLETED SCAN";
        const blockers = Object.entries(autonomy.last_rejection_counts || {})
            .sort((a, b) => Number(b[1]) - Number(a[1]));
        const marks = Object.entries(autonomy.last_mark_rejection_counts || {});
        const blockerText = blockers.length
            ? blockers.map(([name, count]) => `${name.replaceAll("_", " ")}: ${count}`).join(" · ")
            : "No entry rejection telemetry yet.";
        const markText = marks.length
            ? ` Mark safety: ${marks.map(([name, count]) => `${name}: ${count}`).join(" · ")}.`
            : "";
        const exposureSummary = [
            `asset ${Object.keys(portfolio.asset_class_exposure || {}).length}`,
            `strategy ${Object.keys(portfolio.strategy_exposure || {}).length}`,
            `direction ${Object.keys(portfolio.direction_exposure || {}).length}`
        ].join(" · ");
        document.getElementById("paperBlockers").textContent =
            `Profile ${autonomy.profile || "—"} · ${Number(autonomy.scan_cycles || 0)} scans · ${Number(autonomy.positions_opened || 0)} opened · ${Number(autonomy.positions_closed || 0)} closed. `
            + `Exposure groups: ${exposureSummary}. Entry locks: ${locks.join(", ") || "none"}. ${blockerText}.${markText}`;
    } catch (error) {
        document.getElementById("paperRunState").textContent = "TELEMETRY DEGRADED";
        document.getElementById("paperBlockers").textContent = error.message;
    }
}


function companyRow(className, values) {
    const row = document.createElement("div");
    row.className = className;
    values.forEach((value, index) => {
        const cell = index === 0 ? document.createElement("strong") : document.createElement("span");
        cell.textContent = String(value ?? "—");
        row.appendChild(cell);
    });
    return row;
}


async function refreshCompanyOS() {
    const companyWindow = document.getElementById("win-company");
    if (!companyWindow || companyWindow.style.display === "none") return;
    try {
        const state = await api("/api/company-os");
        const plan = state.latest_plan || null;
        document.getElementById("companyAgentCount").textContent = Number(state.agent_count || 0);
        document.getElementById("companyAutopilot").textContent =
            plan?.autopilot?.status || state.autonomy || "SUPERVISED";
        if (!plan) return;

        const research = plan.research_program || {};
        const tracks = Array.isArray(research.research_tracks) ? research.research_tracks : [];
        const orders = Array.isArray(research.department_work_orders) ? research.department_work_orders : [];
        const departmentRun = plan.department_run || null;
        const departmentResults = Array.isArray(departmentRun?.results) ? departmentRun.results : [];
        const horizons = Array.isArray(research.horizons) ? research.horizons : [];
        const approvals = Array.isArray(plan.tasks)
            ? plan.tasks.filter(item => item.approval_required).length
            : 0;
        document.getElementById("companyName").textContent = plan.company_name || "ACTIVE VENTURE";
        document.getElementById("companyMission").textContent = plan.venture_thesis?.mission || plan.idea || "—";
        document.getElementById("companyTrackCount").textContent = tracks.length;
        document.getElementById("companyArtifactCount").textContent = Array.isArray(plan.artifacts) ? plan.artifacts.length : 0;
        document.getElementById("companyApprovalCount").textContent = approvals;

        const workboard = document.getElementById("companyWorkboard");
        workboard.innerHTML = "";
        if (departmentResults.length) {
            departmentResults.forEach(item => workboard.appendChild(companyRow("companyWorkRow", [
                String(item.department_id || "DEPARTMENT").replaceAll("_", " ").toUpperCase(),
                String(item.status || "UNKNOWN"),
                item.message || "No local brief was produced."
            ])));
        } else {
            orders.forEach(item => workboard.appendChild(companyRow("companyWorkRow", [
                item.id, String(item.agent || "").toUpperCase(), `${item.status} · ${item.deliverable}`
            ])));
        }
        if (!orders.length && !departmentResults.length) workboard.textContent = "No department work orders.";

        const roadmap = document.getElementById("companyRoadmap");
        roadmap.innerHTML = "";
        horizons.forEach(item => roadmap.appendChild(companyRow("companyRoadmapRow", [
            item.horizon, item.gate, item.outcome
        ])));
        if (!horizons.length) roadmap.textContent = "No long-horizon roadmap.";

        const hypotheses = Array.isArray(research.hypotheses) ? research.hypotheses : [];
        const obstacles = Array.isArray(research.obstacle_register) ? research.obstacle_register : [];
        const actionQueue = state.external_action_queue || {};
        const actionCounts = actionQueue.counts || {};
        const queuedActions = Array.isArray(actionQueue.actions) ? actionQueue.actions.length : 0;
        const radar = state.opportunity_radar_schedule || plan.opportunity_radar_schedule || {};
        document.getElementById("companyResearchState").textContent =
            `${research.truth_policy || "HYPOTHESES ARE NOT FACTS"} · ${hypotheses.length} hypotheses · ${obstacles.length} obstacle classes · `
            + `background research ${plan.autopilot?.research || "NOT STARTED"}; `
            + `department specialists ${plan.autopilot?.department_specialists || plan.autopilot?.department_workboard || "NOT STARTED"}. `
            + `Opportunity radar ${radar.last_status || "ENROLLED"}, next due ${radar.next_due_at || "—"}. `
            + `External queue ${queuedActions} exact drafts (${Number(actionCounts.DRAFT_REVIEW_REQUIRED || 0)} awaiting review); nothing executed. `
            + `Publishing, accounts, spending, contracts, hiring, production deployment, outreach and live trading remain approval-gated.`;
    } catch (error) {
        document.getElementById("companyAutopilot").textContent = "DEGRADED";
        document.getElementById("companyResearchState").textContent = error.message;
    }
}


async function refreshEvidence() {

    try {

        const rows =
            await api(
                "/api/evidence"
            );


        const holder =
            document.getElementById(
                "evidenceFeed"
            );


        const activity =
            document.getElementById(
                "activityFeed"
            );


        holder.innerHTML = "";

        activity.innerHTML = "";


        const values =
            (
                Array.isArray(
                    rows
                )
                ? rows
                : []
            )
            .slice(
                -30
            )
            .reverse();


        for (
            const row
            of values
        ) {

            const item =
                document.createElement(
                    "div"
                );


            item.className =
                "feedItem";


            const title =
                document.createElement(
                    "div"
                );


            title.className =
                "feedTitle";


            title.textContent =
                row.event
                || row.goal
                || "ACTIVITY";


            const meta =
                document.createElement(
                    "div"
                );


            meta.className =
                "feedMeta";


            meta.textContent =
                row.timestamp
                || "";


            item.append(
                title,
                meta
            );


            holder.appendChild(
                item
            );


            activity.appendChild(
                item.cloneNode(
                    true
                )
            );
        }


    } catch (_) {}


    try {

        const value =
            await api(
                "/api/approvals"
            );


        const holder =
            document.getElementById(
                "approvalFeed"
            );


        holder.innerHTML = "";


        const rows =
            Array.isArray(
                value
            )
            ? value
            : (
                Array.isArray(
                    value.approvals
                )
                ? value.approvals
                : []
            );


        if (!rows.length) {

            holder.innerHTML =
                '<div class="feedItem">'
                + '<div class="feedTitle">'
                + 'NO PENDING APPROVALS'
                + '</div>'
                + '<div class="feedMeta">'
                + 'Approval gate remains armed.'
                + '</div>'
                + '</div>';

            return;
        }


        for (
            const row
            of rows.slice(
                0,
                20
            )
        ) {

            const item =
                document.createElement(
                    "div"
                );


            item.className =
                "feedItem";


            item.textContent =
                JSON.stringify(
                    row
                );


            holder.appendChild(
                item
            );
        }


    } catch (_) {}
}


function setupVoice() {

    const Recognition =
        window.SpeechRecognition
        || window.webkitSpeechRecognition;


    if (!Recognition) {

        document.getElementById(
            "listenButton"
        ).textContent =
            "MIC N/A";

        return;
    }


    recognition =
        new Recognition();


    recognition.lang =
        "en-IN";

    recognition.interimResults =
        true;

    recognition.continuous =
        false;


    recognition.onstart =
        () => {

            setCoreState(
                "listening"
            );


            document.getElementById(
                "voiceState"
            ).textContent =
                "● LISTENING";
        };


    recognition.onresult =
        event => {

            let text = "";


            for (
                let i =
                    event.resultIndex;

                i <
                    event.results.length;

                i++
            ) {

                text +=
                    event.results[
                        i
                    ][0]
                    .transcript;
            }


            document.getElementById(
                "commandInput"
            ).value =
                text;
        };


    recognition.onend =
        () => {

            document.getElementById(
                "voiceState"
            ).textContent =
                "● VOICE READY";


            setCoreState(
                "ready"
            );
        };
}


function drawCore() {

    const canvas =
        document.getElementById(
            "coreCanvas"
        );


    const context =
        canvas.getContext(
            "2d"
        );


    let tick = 0;


    function frame() {

        const ratio =
            window.devicePixelRatio
            || 1;


        const rect =
            canvas.getBoundingClientRect();


        if (
            canvas.width
            !== Math.round(
                rect.width
                * ratio
            )
        ) {

            canvas.width =
                rect.width
                * ratio;

            canvas.height =
                rect.height
                * ratio;


            context.setTransform(
                ratio,
                0,
                0,
                ratio,
                0,
                0
            );
        }


        const width =
            rect.width;

        const height =
            rect.height;


        const cx =
            width / 2;

        const cy =
            height / 2;


        context.clearRect(
            0,
            0,
            width,
            height
        );


        const gradient =
            context
            .createRadialGradient(
                cx,
                cy,
                5,
                cx,
                cy,
                width * .42
            );


        const state =
            document.body
                .dataset
                .coreState;


        const primary =
            (
                state === "thinking"
                ? "150,94,255"
                : (
                    state === "error"
                    ? "255,77,96"
                    : (
                        state === "approval"
                        ? "255,196,69"
                        : "74,204,255"
                    )
                )
            );


        gradient.addColorStop(
            0,
            `rgba(${primary},.40)`
        );

        gradient.addColorStop(
            .38,
            `rgba(${primary},.10)`
        );

        gradient.addColorStop(
            1,
            `rgba(${primary},0)`
        );


        context.fillStyle =
            gradient;


        context.beginPath();

        context.arc(
            cx,
            cy,
            width * .43,
            0,
            Math.PI * 2
        );

        context.fill();


        for (
            let ring = 0;
            ring < 6;
            ring++
        ) {

            context.save();

            context.translate(
                cx,
                cy
            );


            context.rotate(
                tick
                * (
                    .0016
                    + ring
                    * .00065
                )
                * (
                    ring % 2
                    ? -1
                    : 1
                )
            );


            context.strokeStyle =
                `rgba(
                    ${primary},
                    ${
                        .16
                        + ring * .04
                    }
                )`;


            context.lineWidth =
                1;


            context.beginPath();


            context.ellipse(
                0,
                0,
                width
                * (
                    .19
                    + ring
                    * .035
                ),
                height
                * (
                    .09
                    + ring
                    * .027
                ),
                ring * .48,
                0,
                Math.PI * 2
            );


            context.stroke();

            context.restore();
        }


        const agentTotal =
            Math.max(
                12,
                Number(
                    document
                    .getElementById(
                        "agentCount"
                    )
                    .textContent
                )
                || 18
            );


        for (
            let i = 0;
            i < agentTotal;
            i++
        ) {

            const angle =
                tick * .002
                + i
                * Math.PI
                * 2
                / agentTotal;


            const radius =
                width
                * (
                    .27
                    + .04
                    * Math.sin(
                        tick
                        * .007
                        + i
                    )
                );


            const x =
                cx
                + Math.cos(
                    angle
                )
                * radius;


            const y =
                cy
                + Math.sin(
                    angle
                )
                * radius
                * .52;


            context.fillStyle =
                (
                    i % 7 === 0
                    ? "#70f5a9"
                    : `rgb(${primary})`
                );


            context.beginPath();

            context.arc(
                x,
                y,
                (
                    i % 7 === 0
                    ? 2.4
                    : 1.2
                ),
                0,
                Math.PI * 2
            );

            context.fill();
        }


        tick++;


        requestAnimationFrame(
            frame
        );
    }


    frame();
}


function bindWindows() {

    document
        .querySelectorAll(
            ".jarvisWindow"
        )
        .forEach(
            win => {

                makeDraggable(
                    win
                );


                const close =
                    win.querySelector(
                        "[data-close]"
                    );


                if (close) {

                    close.onclick =
                        () =>
                            closeWindow(
                                win.dataset.window
                            );
                }


                const minimize =
                    win.querySelector(
                        "[data-minimize]"
                    );


                if (minimize) {

                    minimize.onclick =
                        () => {

                            win.classList.toggle(
                                "minimized"
                            );


                            persistWorkspace();
                        };
                }


                const maximize =
                    win.querySelector(
                        "[data-maximize]"
                    );


                if (maximize) {

                    maximize.onclick =
                        () => {

                            win.classList.toggle(
                                "maximized"
                            );


                            focusWindow(
                                win
                            );
                        };
                }
            }
        );


    document
        .querySelectorAll(
            "[data-open]"
        )
        .forEach(
            button => {

                button.onclick =
                    () =>
                        openWindow(
                            button.dataset.open
                        );
            }
        );


    document
        .querySelectorAll(
            "[data-layout]"
        )
        .forEach(
            button => {

                button.onclick =
                    () =>
                        applyLayout(
                            button.dataset.layout
                        );
            }
        );
}


function bindChartControls() {

    document
        .getElementById(
            "chartSymbol"
        )
        .addEventListener(
            "change",
            event => {

                chartSlots[0] = {
                    symbol:
                        event.target.value,

                    timeframe:
                        selectedTimeframe
                };


                renderChartSlots();
            }
        );


    document
        .querySelectorAll(
            "[data-timeframe]"
        )
        .forEach(
            button => {

                button.onclick =
                    () => {

                        selectedTimeframe =
                            button
                            .dataset
                            .timeframe;


                        document
                            .querySelectorAll(
                                "[data-timeframe]"
                            )
                            .forEach(
                                item =>
                                    item
                                    .classList
                                    .remove(
                                        "selected"
                                    )
                            );


                        button
                            .classList
                            .add(
                                "selected"
                            );


                        chartSlots =
                            chartSlots.map(
                                slot => ({
                                    ...slot,
                                    timeframe:
                                        selectedTimeframe
                                })
                            );


                        renderChartSlots();
                    };
            }
        );


    document
        .getElementById(
            "refreshChart"
        )
        .onclick =
            () =>
                renderChartSlots();
}


document
    .getElementById(
        "executeButton"
    )
    .onclick =
        () =>
            executeCommand();


document
    .getElementById(
        "commandInput"
    )
    .addEventListener(
        "keydown",
        event => {

            if (
                event.key
                === "Enter"
            ) {

                executeCommand();
            }
        }
    );


document
    .getElementById(
        "listenButton"
    )
    .onclick =
        () => {

            if (recognition) {

                recognition.start();
            }
        };


document
    .getElementById(
        "stopButton"
    )
    .onclick =
        () => {

            if (recognition) {

                try {

                    recognition.stop();

                } catch (_) {}
            }


            speechSynthesis.cancel();


            setCoreState(
                "ready"
            );
        };


document
    .getElementById(
        "fullscreenButton"
    )
    .onclick =
        async () => {

            try {

                if (
                    !document.fullscreenElement
                ) {

                    await document
                        .documentElement
                        .requestFullscreen();

                } else {

                    await document
                        .exitFullscreen();
                }

            } catch (_) {}
        };


document
    .getElementById(
        "saveWorkspace"
    )
    .onclick =
        () => {

            persistWorkspace();


            addConversation(
                "JARVIS",
                "Workspace layout saved locally.",
                "WORKSPACE"
            );
        };


bindWindows();

bindCommandButtons();

bindChartControls();

restoreWorkspace();

/* Legacy setupVoice disabled: V3.1.6B2 owns microphone recognition. */

drawCore();

renderChartSlots();

refreshStatus();

refreshMarket();

refreshEvidence();

refreshPaperPortfolio();

refreshCompanyOS();


setInterval(
    refreshStatus,
    5000
);

setInterval(
    refreshMarket,
    10000
);

setInterval(
    refreshEvidence,
    6000
);

setInterval(
    refreshPaperPortfolio,
    2500
);

setInterval(
    refreshCompanyOS,
    4000
);


window.addEventListener(
    "resize",
    () =>
        renderChartSlots()
);


/*
JARVIS_V315_VOICE_CONVERSATION
Compatibility marker retained for previous regression tests.
*/

/* JARVIS_V316B2_CONVERSATIONAL_VOICE */

(() => {

    "use strict";


    const SpeechRecognition =
        window.SpeechRecognition
        || window.webkitSpeechRecognition;


    const J = {

        enabled:
            true,

        recognition:
            null,

        listening:
            false,

        speaking:
            false,

        awaitingCommand:
            false,

        commandDeadline:
            0,

        lastTranscript:
            "",

        lastTranscriptAt:
            0,

        restartTimer:
            null,

        speechMode:
            "short",

        lastAssistantText:
            "",

        speechEndedAt:
            0,

        echoBlockUntil:
            0,

        followupDeadline:
            0,

        nativeControlAvailable:
            false,

        nativeLastEventId:
            0,

        nativePollTimer:
            null,

        nativeBaseUrl:
            "http://127.0.0.1:8798",

    };


const depthButton = document.getElementById("depthButton");
const depthPreference = localStorage.getItem("jarvis-spatial-depth");
document.body.classList.toggle("spatial-mode", depthPreference !== "off");
if (depthButton) {
    depthButton.setAttribute("aria-pressed", String(depthPreference !== "off"));
    depthButton.onclick = () => {
        const enabled = !document.body.classList.contains("spatial-mode");
        document.body.classList.toggle("spatial-mode", enabled);
        depthButton.setAttribute("aria-pressed", String(enabled));
        localStorage.setItem("jarvis-spatial-depth", enabled ? "on" : "off");
    };
}

window.addEventListener("pointermove", event => {
    if (!document.body.classList.contains("spatial-mode")) return;
    const x = (event.clientX / Math.max(window.innerWidth, 1) - .5) * 2;
    const y = (event.clientY / Math.max(window.innerHeight, 1) - .5) * 2;
    document.documentElement.style.setProperty("--depth-x", `${(x * 18).toFixed(2)}px`);
    document.documentElement.style.setProperty("--depth-y", `${(y * 12).toFixed(2)}px`);
    document.documentElement.style.setProperty("--shadow-x", `${(x * -10).toFixed(2)}px`);
}, {passive: true});


    window.JARVISVoice = J;


    // ========================================================
    // DOM
    // ========================================================

    function inputBox() {

        return (
            document.getElementById(
                "commandInput"
            )
            ||
            document.querySelector(
                "textarea,input"
            )
        );
    }


    function executeButton() {

        return (
            document.getElementById(
                "executeButton"
            )
            ||
            Array.from(
                document.querySelectorAll(
                    "button"
                )
            ).find(
                b =>
                    /^(execute|send)\b/i.test(
                        (
                            b.innerText
                            || b.textContent
                            || ""
                        ).trim()
                    )
            )
            ||
            null
        );
    }


    function setVoiceState(
        value
    ) {

        document.documentElement.dataset.jarvisVoiceState =
            value;


        const stateElement =
            document.getElementById(
                "voiceState"
            );


        if (stateElement) {

            const names = {

                ready:
                    "● VOICE READY",

                listening:
                    "● LISTENING",

                speaking:
                    "● SPEAKING",

                thinking:
                    "● THINKING",

                interrupted:
                    "● I'M LISTENING",

                off:
                    "● VOICE OFF",

            };


            stateElement.textContent =
                names[value]
                || value.toUpperCase();
        }


        if (
            typeof setCoreState
            === "function"
        ) {

            if (
                value === "listening"
                || value === "thinking"
            ) {

                setCoreState(
                    value
                );

            }
            else if (
                value === "ready"
                || value === "interrupted"
            ) {

                setCoreState(
                    "ready"
                );
            }
        }
    }


    // ========================================================
    // NATURAL RESPONSE GENERATOR
    // ========================================================

    function field(
        text,
        label
    ) {

        const match =
            String(text || "").match(
                new RegExp(
                    "^\\s*"
                    + label
                    + "\\s*:\\s*(.+)$",
                    "im"
                )
            );


        return (
            match
            ? match[1].trim()
            : null
        );
    }


    function tradingSpeech(
        text
    ) {

        const symbol =
            field(
                text,
                "Symbol"
            );


        if (!symbol) {

            return null;
        }


        const timeframe =
            field(
                text,
                "Timeframe"
            );


        const trend =
            field(
                text,
                "Trend"
            );


        const momentum =
            field(
                text,
                "Momentum"
            );


        const decision =
            field(
                text,
                "Decision"
            );


        const confidence =
            field(
                text,
                "Confidence Score"
            );


        const entry =
            field(
                text,
                "Entry"
            );


        const stop =
            field(
                text,
                "Stop Loss"
            );


        const rsi =
            field(
                text,
                "RSI"
            );


        const adx =
            field(
                text,
                "ADX"
            );


        const parts = [];


        let intro =
            symbol;


        if (timeframe) {

            intro +=
                " on the "
                + timeframe
                + " timeframe";
        }


        if (trend) {

            intro +=
                " looks "
                + trend.toLowerCase();
        }


        intro += ".";


        parts.push(
            intro
        );


        if (
            momentum
            &&
            momentum.toUpperCase()
            !== "NEUTRAL"
        ) {

            parts.push(
                "Momentum is "
                + momentum.toLowerCase()
                + "."
            );
        }


        if (
            decision
            &&
            decision.toUpperCase()
            === "WAIT"
        ) {

            parts.push(
                "I don't see a clean trade setup right now, so I'd wait for better confirmation."
            );

        }
        else if (decision) {

            let sentence =
                "The current setup is "
                + decision.toLowerCase();


            if (confidence) {

                sentence +=
                    " with a setup score of "
                    + confidence;
            }


            sentence += ".";


            parts.push(
                sentence
            );
        }


        if (
            entry
            &&
            entry.toUpperCase()
            !== "N/A"
        ) {

            let levels =
                "The entry area is around "
                + entry.replace(
                    /,/g,
                    ""
                );


            if (
                stop
                &&
                stop.toUpperCase()
                !== "N/A"
            ) {

                levels +=
                    ", with invalidation near "
                    + stop.replace(
                        /,/g,
                        ""
                    );
            }


            levels += ".";


            parts.push(
                levels
            );
        }


        // RSI/ADX remain available on-screen.
        // They are spoken only in detailed mode.
        if (
            J.speechMode
            === "detailed"
            &&
            (
                rsi
                ||
                adx
            )
        ) {

            let detail =
                "For context";


            if (rsi) {

                detail +=
                    ", RSI is "
                    + rsi;
            }


            if (adx) {

                detail +=
                    ", and ADX is "
                    + adx;
            }


            detail += ".";


            parts.push(
                detail
            );
        }


        return parts.join(
            " "
        );
    }


    function genericSpeech(
        text
    ) {

        let value =
            String(
                text
                || ""
            );


        value = value
            .replace(
                /```[\s\S]*?```/g,
                " "
            )
            .replace(
                /^[-=_*]{3,}\s*$/gm,
                ""
            )
            .replace(
                /^#{1,6}\s+/gm,
                ""
            )
            .replace(
                /^\s*[A-Z][A-Z0-9 _\/-]{5,}\s*$/gm,
                ""
            )
            .replace(
                /^\s*[-*?]\s+/gm,
                ""
            )
            .replace(
                /\*\*/g,
                ""
            )
            .replace(
                /\s+/g,
                " "
            )
            .trim();


        if (!value) {

            return "";
        }


        const sentences =
            value.match(
                /[^.!?]+[.!?]+|[^.!?]+$/g
            )
            || [
                value
            ];


        const count =
            (
                J.speechMode
                === "detailed"
                ? 6
                : (
                    J.speechMode
                    === "normal"
                    ? 4
                    : 2
                )
            );


        return sentences
            .slice(
                0,
                count
            )
            .join(
                " "
            )
            .trim();
    }


    function spokenVersion(
        text
    ) {

        const value =
            String(
                text
                || ""
            ).trim();


        if (!value) {

            return "";
        }


        if (
            /JARVIS TRADING ANALYSIS/i.test(
                value
            )
        ) {

            const trading =
                tradingSpeech(
                    value
                );


            if (trading) {

                return trading;
            }
        }


        return genericSpeech(
            value
        );
    }


    // ========================================================
    // JARVIS V3.2 HYBRID NATIVE CONTROL
    //
    // Browser SpeechRecognition owns normal dictation while
    // JARVIS is silent. During TTS it is deliberately suspended
    // so speaker audio cannot become a normal command.
    //
    // A tiny native Windows recognizer listens only for control
    // phrases such as "Jarvis" and "Stop". This keeps barge-in
    // available without running two full dictation recognizers.
    // ========================================================

    /* JARVIS_V32_HYBRID_VOICE */

    async function nativeRequest(
        path,
        options = {}
    ) {

        try {

            const response =
                await fetch(
                    J.nativeBaseUrl
                    + path,
                    {
                        ...options,
                        cache:
                            "no-store",
                    }
                );


            if (!response.ok) {

                throw new Error(
                    "native voice HTTP "
                    + response.status
                );
            }


            J.nativeControlAvailable =
                true;


            return await response.json();

        }
        catch (_) {

            J.nativeControlAvailable =
                false;


            return null;
        }
    }


    function nativeSpeakingState(
        speaking
    ) {

        nativeRequest(
            "/state",
            {
                method:
                    "POST",

                headers:
                    {
                        "Content-Type":
                            "application/json",
                    },

                body:
                    JSON.stringify(
                        {
                            speaking:
                                Boolean(
                                    speaking
                                ),
                        }
                    ),
            }
        );
    }


    function suspendRecognition() {

        clearTimeout(
            J.restartTimer
        );


        if (!J.recognition) {

            return;
        }


        try {

            J.recognition.abort();

        }
        catch (_) {

        }


        J.listening =
            false;
    }


    function handleNativeEvent(
        event
    ) {

        if (!event) {

            return;
        }


        const id =
            Number(
                event.id
                || 0
            );


        if (
            id
            > J.nativeLastEventId
        ) {

            J.nativeLastEventId =
                id;
        }


        const type =
            String(
                event.type
                || ""
            )
            .toLowerCase();


        if (
            type
            === "stop"
        ) {

            interrupt();


            return;
        }


        if (
            type
            === "wake"
            &&
            !J.speaking
        ) {

            greet();
        }
    }


    async function pollNativeControl() {

        if (!J.enabled) {

            return;
        }


        const payload =
            await nativeRequest(
                "/events?after="
                + encodeURIComponent(
                    String(
                        J.nativeLastEventId
                    )
                )
            );


        if (
            payload
            &&
            Array.isArray(
                payload.events
            )
        ) {

            for (
                const event
                of payload.events
            ) {

                handleNativeEvent(
                    event
                );
            }
        }
    }


    async function initNativeControl() {

        const health =
            await nativeRequest(
                "/health"
            );


        J.nativeControlAvailable =
            Boolean(
                health
                &&
                health.success
            );


        clearInterval(
            J.nativePollTimer
        );


        J.nativePollTimer =
            setInterval(
                pollNativeControl,
                180
            );


        nativeSpeakingState(
            J.speaking
        );
    }


    // ========================================================
    // SPEAK
    // ========================================================

    function selectVoice() {

        const voices =
            window.speechSynthesis
                ?.getVoices?.()
            || [];


        return (
            voices.find(
                v =>
                    /^en-IN$/i.test(
                        v.lang
                    )
            )
            ||
            voices.find(
                v =>
                    /^en-GB$/i.test(
                        v.lang
                    )
            )
            ||
            voices.find(
                v =>
                    /^en/i.test(
                        v.lang
                    )
            )
            ||
            null
        );
    }


    function cancelSpeech() {

        if (
            window.speechSynthesis
        ) {

            window.speechSynthesis.cancel();
        }


        J.speaking =
            false;


        nativeSpeakingState(
            false
        );
    }


    function speak(
        text,
        options = {}
    ) {

        const raw =
            options.raw
            === true;


        const resume =
            options.resume
            !== false;


        const value =
            (
                raw
                ? String(
                    text
                    || ""
                ).trim()
                : spokenVersion(
                    text
                )
            );


        if (
            !value
            ||
            !window.speechSynthesis
        ) {

            if (resume) {

                scheduleListen(
                    250
                );
            }


            return;
        }


        cancelSpeech();


        J.speaking =
            true;


        J.lastAssistantText =
            value;


        const utterance =
            new SpeechSynthesisUtterance(
                value
            );


        utterance.lang =
            "en-IN";


        utterance.rate =
            1.04;


        utterance.pitch =
            0.97;


        utterance.volume =
            0.82;


        const voice =
            selectVoice();


        if (voice) {

            utterance.voice =
                voice;
        }


        utterance.onstart =
            () => {

                J.speaking =
                    true;


                J.echoBlockUntil =
                    0;


                setVoiceState(
                    "speaking"
                );


                // Half-duplex dictation boundary:
                // browser dictation is OFF while TTS is audible.
                // Native control recognition remains available
                // for "Stop" / wake control phrases.
                suspendRecognition();


                nativeSpeakingState(
                    true
                );
            };


        utterance.onend =
            () => {

                J.speaking =
                    false;


                J.speechEndedAt =
                    Date.now();


                // Chrome can emit the speaker audio as a final
                // microphone transcript just AFTER TTS ends.
                // Quarantine this late echo before accepting
                // another normal conversational sentence.
                J.echoBlockUntil =
                    J.speechEndedAt
                    + 1600;


                // Natural follow-up window.
                J.followupDeadline =
                    J.speechEndedAt
                    + 10000;


                nativeSpeakingState(
                    false
                );


                setVoiceState(
                    "ready"
                );


                if (resume) {

                    scheduleListen(
                        450
                    );
                }
            };


        utterance.onerror =
            () => {

                J.speaking =
                    false;


                nativeSpeakingState(
                    false
                );


                if (resume) {

                    scheduleListen(
                        450
                    );
                }
            };


        window.speechSynthesis.speak(
            utterance
        );
    }


    // ========================================================
    // COMMAND EXECUTION
    // ========================================================

    function submitCommand(
        text,
        confidence = null
    ) {

        const value =
            String(
                text
                || ""
            ).trim();


        if (!value) {

            return false;
        }


        if (commandInFlight) {

            console.debug(
                "JARVIS voice command deferred while busy:",
                value
            );


            return false;
        }


        const input =
            inputBox();


        const execute =
            executeButton();


        if (
            !input
            ||
            !execute
        ) {

            speak(
                "I can't access the command console.",
                {
                    raw:
                        true,
                }
            );


            return false;
        }


        J.awaitingCommand =
            false;


        setVoiceState(
            "thinking"
        );


        input.value = value;


        executeCommand(
            value,
            {
                inputMode: "voice",
                speechConfidence: confidence,
            }
        );


        return true;
    }


    // ========================================================
    // WAKE / INTERRUPTION
    // ========================================================

    function greet() {

        J.awaitingCommand =
            true;


        J.commandDeadline =
            Date.now()
            + 15000;


        cancelSpeech();


        speak(
            "Hi. What can I do for you?",
            {
                raw:
                    true,
            }
        );
    }


    function interrupt(
        command = ""
    ) {

        cancelSpeech();


        setVoiceState(
            "interrupted"
        );


        const value =
            String(
                command
                || ""
            ).trim();


        if (value) {

            setTimeout(
                () => {

                    submitCommand(
                        value
                    );

                },
                80
            );


            return;
        }


        J.awaitingCommand =
            true;


        J.commandDeadline =
            Date.now()
            + 15000;


        scheduleListen(
            40
        );
    }


    // ========================================================
    // ECHO FILTER
    // ========================================================

    function normalizeForEcho(
        value
    ) {

        return String(
            value
            || ""
        )
        .toLowerCase()
        .replace(
            /[^a-z0-9\s]/g,
            " "
        )
        .replace(
            /\s+/g,
            " "
        )
        .trim();
    }


    function looksLikeJarvisEcho(
        transcript
    ) {

        const heard =
            normalizeForEcho(
                transcript
            );


        const spoken =
            normalizeForEcho(
                J.lastAssistantText
            );


        if (
            !heard
            ||
            !spoken
        ) {

            return false;
        }


        // Exact/sub-string replay.
        if (
            spoken.includes(
                heard
            )
            ||
            heard.includes(
                spoken
            )
        ) {

            return true;
        }


        const heardWords =
            heard
            .split(" ")
            .filter(Boolean);


        const spokenWords =
            new Set(
                spoken
                .split(" ")
                .filter(Boolean)
            );


        if (
            heardWords.length
            < 3
        ) {

            return false;
        }


        let overlap =
            0;


        for (
            const word
            of heardWords
        ) {

            if (
                spokenWords.has(
                    word
                )
            ) {

                overlap++;
            }
        }


        const ratio =
            overlap
            / heardWords.length;


        return (
            ratio >= 0.60
        );
    }


    // ========================================================
    // TRANSCRIPTS
    // ========================================================

    function processTranscript(
        raw,
        confidence
    ) {

        const transcript =
            String(
                raw
                || ""
            )
            .replace(
                /\s+/g,
                " "
            )
            .trim();


        if (!transcript) {

            return;
        }


        const now =
            Date.now();


        // ----------------------------------------------------
        // ABSOLUTE PRIORITY: STOP / INTERRUPT
        //
        // This runs BEFORE echo filtering and confidence
        // filtering so "stop" can interrupt JARVIS immediately.
        // ----------------------------------------------------

        if (
            /^(?:jarvis[\s,;:\-]+)?(?:stop|stop talking|be quiet|quiet|shut up)$/i
                .test(
                    transcript
                )
        ) {

            interrupt();


            return;
        }


        // Compatibility and quality threshold.
        if (
            Number.isFinite(
                confidence
            )
            &&
            confidence > 0
            &&
            confidence < 0.48
        ) {

            return;
        }


        if (
            transcript.toLowerCase()
            === J.lastTranscript.toLowerCase()
            &&
            now
            - J.lastTranscriptAt
            < 2200
        ) {

            return;
        }


        J.lastTranscript =
            transcript;


        J.lastTranscriptAt =
            now;


        // ----------------------------------------------------
        // While speaking: accept ONLY interruption phrases.
        // Ordinary detected speech is treated as speaker echo.
        // ----------------------------------------------------

        if (J.speaking) {

            const wake =
                transcript.match(
                    /^(?:hey\s+|hello\s+|hi\s+)?jarvis(?:[\s,;:\-]+(.*))?$/i
                );


            if (wake) {

                interrupt(
                    wake[1]
                    || ""
                );


                return;
            }


            if (
                /^(stop|stop talking|quiet|be quiet)$/i
                .test(
                    transcript
                )
            ) {

                interrupt();


                return;
            }


            return;
        }


        // ----------------------------------------------------
        // POST-SPEECH ECHO QUARANTINE
        //
        // Prevent JARVIS from submitting its own sentence after
        // TTS has technically finished.
        // ----------------------------------------------------

        if (
            now
            < J.echoBlockUntil
        ) {

            return;
        }


        if (
            now
            - J.speechEndedAt
            < 4000
            &&
            looksLikeJarvisEcho(
                transcript
            )
        ) {

            console.debug(
                "JARVIS echo suppressed:",
                transcript
            );


            return;
        }


        // ----------------------------------------------------
        // Speech style
        // ----------------------------------------------------

        if (
            /^(jarvis[,\s]+)?(keep it short|be brief|short answers)$/i
                .test(
                    transcript
                )
        ) {

            J.speechMode =
                "short";


            speak(
                "Sure. I'll keep it short.",
                {
                    raw:
                        true,
                }
            );


            return;
        }


        if (
            /^(jarvis[,\s]+)?(normal mode|normal answers)$/i
                .test(
                    transcript
                )
        ) {

            J.speechMode =
                "normal";


            speak(
                "Okay. I'll use normal conversational answers.",
                {
                    raw:
                        true,
                }
            );


            return;
        }


        if (
            /^(jarvis[,\s]+)?(explain more|detail mode|detailed answers)$/i
                .test(
                    transcript
                )
        ) {

            J.speechMode =
                "detailed";


            speak(
                "Sure. I'll explain it in more detail.",
                {
                    raw:
                        true,
                }
            );


            return;
        }


        // ----------------------------------------------------
        // Voice off
        // ----------------------------------------------------

        if (
            /^(jarvis[,\s]+)?(voice off|stop listening)$/i
                .test(
                    transcript
                )
        ) {

            disableVoice();


            return;
        }


        // ----------------------------------------------------
        // "Jarvis"
        // ----------------------------------------------------

        if (
            /^(?:hey\s+|hello\s+|hi\s+)?jarvis[.!?, ]*$/i
                .test(
                    transcript
                )
        ) {

            greet();


            return;
        }


        // ----------------------------------------------------
        // "Jarvis, command..."
        // ----------------------------------------------------

        const wakeCommand =
            transcript.match(
                /^(?:hey\s+|hello\s+|hi\s+)?jarvis[\s,;:\-]+(.+)$/i
            );


        if (
            wakeCommand
            &&
            wakeCommand[
                1
            ]
        ) {

            submitCommand(
                wakeCommand[
                    1
                ],
                confidence
            );


            return;
        }


        // ----------------------------------------------------
        // Next sentence after greeting
        // ----------------------------------------------------

        if (
            J.awaitingCommand
            &&
            now
            <= J.commandDeadline
        ) {

            submitCommand(
                transcript,
                confidence
            );


            return;
        }


        // Continuous follow-up conversation.
        if (
            J.enabled
            &&
            transcript.length
            >= 3
            &&
            now
            <= J.followupDeadline
        ) {

            submitCommand(
                transcript,
                confidence
            );


            return;
        }


        // Outside the conversational follow-up window,
        // ordinary room speech is ignored. Say "Jarvis" again
        // to start a new interaction.
        console.debug(
            "JARVIS ignored non-wake background speech:",
            transcript
        );
    }


    // ========================================================
    // RECOGNITION
    // ========================================================

    function scheduleListen(
        delay = 300
    ) {

        if (
            !J.enabled
            ||
            J.speaking
        ) {

            return;
        }


        clearTimeout(
            J.restartTimer
        );


        J.restartTimer =
            setTimeout(
                startListening,
                delay
            );
    }


    function startListening() {

        if (
            !J.enabled
            ||
            !SpeechRecognition
            ||
            J.listening
            ||
            J.speaking
        ) {

            return;
        }


        if (!J.recognition) {

            const recognition =
                new SpeechRecognition();


            recognition.lang =
                "en-IN";


            recognition.interimResults =
                false;


            recognition.continuous =
                false;


            recognition.maxAlternatives =
                3;


            recognition.onstart =
                () => {

                    J.listening =
                        true;


                    if (!J.speaking) {

                        setVoiceState(
                            "listening"
                        );
                    }
                };


            recognition.onresult =
                event => {

                    const result =
                        event.results[
                            event.results.length
                            - 1
                        ];


                    if (
                        !result
                        ||
                        !result.isFinal
                    ) {

                        return;
                    }


                    const alternative =
                        result[
                            0
                        ];


                    processTranscript(
                        alternative.transcript,
                        alternative.confidence
                    );
                };


            recognition.onerror =
                event => {

                    J.listening =
                        false;


                    if (
                        ![
                            "no-speech",
                            "aborted",
                        ].includes(
                            event.error
                        )
                    ) {

                        console.debug(
                            "JARVIS voice:",
                            event.error
                        );
                    }


                    // Self-heal transient browser recognition failures.
                    // Permission-denied states require user action, but all
                    // other errors should return to the listening loop.
                    if (
                        J.enabled
                        &&
                        !J.speaking
                        &&
                        ![
                            "not-allowed",
                            "service-not-allowed",
                        ].includes(
                            event.error
                        )
                    ) {

                        scheduleListen(
                            650
                        );
                    }
                };


            recognition.onend =
                () => {

                    J.listening =
                        false;


                    if (
                        J.enabled
                        &&
                        !J.speaking
                    ) {

                        scheduleListen(
                            330
                        );
                    }
                };


            J.recognition =
                recognition;
        }


        try {

            J.recognition.start();

        }
        catch (_) {

            scheduleListen(
                550
            );
        }
    }


    // ========================================================
    // RESPONSE EXTRACTION
    // ========================================================

    function responseText(
        value,
        depth = 0
    ) {

        if (
            value == null
            ||
            depth > 6
        ) {

            return null;
        }


        if (
            typeof value
            === "string"
        ) {

            return (
                value.length > 1
                ? value
                : null
            );
        }


        if (
            Array.isArray(
                value
            )
        ) {

            for (
                const item
                of value
            ) {

                const result =
                    responseText(
                        item,
                        depth + 1
                    );


                if (result) {

                    return result;
                }
            }


            return null;
        }


        if (
            typeof value
            !== "object"
        ) {

            return null;
        }


        for (
            const key
            of [
                "response",
                "answer",
                "reply",
                "assistant_response",
                "message",
                "text",
                "result",
            ]
        ) {

            if (!(key in value)) {

                continue;
            }


            const result =
                responseText(
                    value[
                        key
                    ],
                    depth + 1
                );


            if (result) {

                return result;
            }
        }


        return null;
    }


    // ========================================================
    // SPEAK ONLY COMMAND RESPONSES
    // ========================================================

    const originalFetch =
        window.fetch.bind(
            window
        );


    window.fetch =
        async function(
            input,
            init = {}
        ) {

            const response =
                await originalFetch(
                    input,
                    init
                );


            try {

                const url =
                    (
                        typeof input
                        === "string"
                        ? input
                        : (
                            input?.url
                            || ""
                        )
                    );


                const method =
                    String(
                        init?.method
                        || "GET"
                    ).toUpperCase();


                // Critical:
                // do NOT speak status/market/evidence POSTs.
                // Only speak actual Master JARVIS commands.
                if (
                    method
                    === "POST"
                    &&
                    url.includes(
                        "/api/command"
                    )
                ) {

                    const clone =
                        response.clone();


                    clone
                        .json()
                        .then(
                            payload => {

                                const text =
                                    responseText(
                                        payload
                                    );


                                if (text) {

                                    speak(
                                        text
                                    );

                                }
                                else {

                                    scheduleListen(
                                        250
                                    );
                                }
                            }
                        )
                        .catch(
                            () => {

                                scheduleListen(
                                    300
                                );
                            }
                        );
                }
            }
            catch (_) {

            }


            return response;
        };


    // ========================================================
    // ENABLE / DISABLE
    // ========================================================

    function enableVoice() {

        J.enabled =
            true;


        setVoiceState(
            "ready"
        );


        initNativeControl();


        scheduleListen(
            150
        );
    }


    function disableVoice() {

        J.enabled =
            false;


        J.awaitingCommand =
            false;


        clearTimeout(
            J.restartTimer
        );


        clearInterval(
            J.nativePollTimer
        );


        J.nativePollTimer =
            null;


        cancelSpeech();


        if (
            J.recognition
        ) {

            try {

                J.recognition.stop();

            }
            catch (_) {

            }
        }


        setVoiceState(
            "off"
        );
    }


    window.enableJarvisVoice =
        enableVoice;


    window.disableJarvisVoice =
        disableVoice;


    window.interruptJarvis =
        interrupt;


    window.jarvisSpeak =
        speak;


    // LISTEN now starts conversational voice,
    // not the disabled legacy recognizer.
    const listen =
        document.getElementById(
            "listenButton"
        );


    if (listen) {

        listen.onclick =
            () => {

                enableVoice();
            };
    }


    const stop =
        document.getElementById(
            "stopButton"
        );


    if (stop) {

        stop.onclick =
            () => {

                disableVoice();


                if (
                    typeof setCoreState
                    === "function"
                ) {

                    setCoreState(
                        "ready"
                    );
                }
            };
    }


    // Emergency toggle.
    document.addEventListener(
        "keydown",
        event => {

            if (
                event.altKey
                &&
                event.key.toLowerCase()
                === "j"
            ) {

                if (J.enabled) {

                    disableVoice();

                }
                else {

                    enableVoice();
                }
            }
        }
    );


    window.addEventListener(
        "load",
        () => {

            setTimeout(
                () => {

                    if (
                        SpeechRecognition
                    ) {

                        enableVoice();
                    }
                },
                900
            );
        }
    );


})();

/* JARVIS_V6_TERMINAL_X_JS */
(function () {
    "use strict";

    function make(tag, className, text) {
        const el = document.createElement(tag);
        if (className) el.className = className;
        if (text !== undefined && text !== null) el.textContent = text;
        return el;
    }

    function setActiveRail(mode) {
        document.querySelectorAll(".v6x-rail-button").forEach((button) => {
            button.classList.toggle("active", button.dataset.mode === mode);
        });
    }

    function setHeader(mode) {
        const title = document.getElementById("v6x-mode-title");
        const sub = document.getElementById("v6x-mode-sub");

        const labels = {
            home: ["JARVIS CORE", "Unified intelligence workspace"],
            chart: ["MARKET CANVAS", "Verified live chart workspace"],
            research: ["INTELLIGENCE", "Research, evidence and synthesis"],
            missions: ["MISSION CONTROL", "Agent orchestration and execution"],
            system: ["SYSTEM", "Runtime, health and safeguards"]
        };

        const value = labels[mode] || labels.home;
        if (title) title.textContent = value[0];
        if (sub) sub.textContent = value[1];
    }

    function hideAllJarvisWindows() {
        document.querySelectorAll(".jarvisWindow").forEach((win) => {
            win.style.display = "none";
            win.classList.remove("minimized", "maximized");
        });
    }

    function showWorkspace(name) {
        const win = document.getElementById("win-" + name);
        if (!win) return null;

        win.style.display = "block";
        win.style.left = "0";
        win.style.top = "0";
        win.style.width = "100%";
        win.style.height = "100%";
        win.style.zIndex = "20";
        win.classList.remove("minimized", "maximized");

        return win;
    }

    window.jarvisV6SetMode = function (mode) {
        if (mode === "trading") {
            window.open(
                "http://127.0.0.1:8787",
                "_blank",
                "noopener"
            );
            return;
        }

        hideAllJarvisWindows();

        const mapping = {
            home: "core",
            chart: "chart",
            research: "research",
            missions: "missions",
            system: "system"
        };

        showWorkspace(mapping[mode] || "core");

        document.body.dataset.v6xMode = mode;
        setActiveRail(mode);
        setHeader(mode);

        try {
            localStorage.setItem("jarvisV6TerminalXMode", mode);
        } catch (_) {}
    };

    function updateClock() {
        const clock = document.getElementById("v6x-clock");
        if (!clock) return;

        clock.textContent = new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit"
        });
    }

    function mirrorRuntimeState() {
        const route = document.getElementById("activeRoute");
        const agents = document.getElementById("agentCount");
        const masterState = document.getElementById("masterState");

        const routeTarget = document.getElementById("v6x-route-value");
        const agentTarget = document.getElementById("v6x-agent-value");
        const stateTarget = document.getElementById("v6x-state-value");

        if (routeTarget && route) {
            routeTarget.textContent = route.textContent || "MASTER";
        }

        if (agentTarget && agents) {
            agentTarget.textContent = agents.textContent || "—";
        }

        if (stateTarget && masterState) {
            stateTarget.textContent = masterState.textContent || "READY";
        }
    }

    function createRailButton(mode, glyph, label) {
        const button = make("button", "v6x-rail-button");
        button.type = "button";
        button.dataset.mode = mode;
        button.title = label;

        const icon = make("span", "v6x-rail-icon", glyph);
        const text = make("span", "v6x-rail-label", label);

        button.append(icon, text);
        button.addEventListener("click", () => {
            window.jarvisV6SetMode(mode);
        });

        return button;
    }

    function initTerminalX() {
        if (document.getElementById("v6x-root")) return;

        const masterConsole = document.getElementById("masterConsole");
        const desktop = document.getElementById("desktop");

        if (!masterConsole || !desktop) {
            console.error("JARVIS V6 Terminal X: required DOM nodes missing");
            return;
        }

        document.body.classList.add("v6x-terminal-active");

        const root = make("div", "v6x-root");
        root.id = "v6x-root";

        const rail = make("aside", "v6x-rail");

        const brand = make("div", "v6x-brand");
        brand.innerHTML = `
            <div class="v6x-brand-orb">
                <span>J</span>
            </div>
            <div class="v6x-brand-pulse"></div>
        `;

        const railNav = make("div", "v6x-rail-nav");
        railNav.append(
            createRailButton("home", "⌂", "CORE"),
            createRailButton("chart", "⌁", "MARKET"),
            createRailButton("research", "◎", "INTEL"),
            createRailButton("missions", "◇", "MISSION"),
            createRailButton("system", "⚙", "SYSTEM")
        );

        const trade = createRailButton("trading", "↗", "QUANT");
        trade.classList.add("v6x-trade-button");

        const railBottom = make("div", "v6x-rail-bottom");
        railBottom.append(trade);

        rail.append(brand, railNav, railBottom);

        const main = make("main", "v6x-main");

        const header = make("header", "v6x-header");

        const headerLeft = make("div", "v6x-header-left");
        const title = make("div", "v6x-mode-title", "JARVIS CORE");
        title.id = "v6x-mode-title";
        const sub = make(
            "div",
            "v6x-mode-sub",
            "Unified intelligence workspace"
        );
        sub.id = "v6x-mode-sub";
        headerLeft.append(title, sub);

        const telemetry = make("div", "v6x-telemetry");

        telemetry.innerHTML = `
            <div class="v6x-telemetry-item">
                <span class="v6x-dot v6x-dot-green"></span>
                <div>
                    <small>STATE</small>
                    <strong id="v6x-state-value">READY</strong>
                </div>
            </div>

            <div class="v6x-telemetry-item">
                <div>
                    <small>ROUTE</small>
                    <strong id="v6x-route-value">MASTER</strong>
                </div>
            </div>

            <div class="v6x-telemetry-item">
                <div>
                    <small>AGENTS</small>
                    <strong id="v6x-agent-value">—</strong>
                </div>
            </div>

            <div class="v6x-telemetry-item v6x-lock">
                <span class="v6x-dot v6x-dot-red"></span>
                <div>
                    <small>LIVE EXECUTION</small>
                    <strong>LOCKED</strong>
                </div>
            </div>

            <div class="v6x-clock" id="v6x-clock">--:--:--</div>
        `;

        header.append(headerLeft, telemetry);

        const stage = make("section", "v6x-stage");

        const backdrop = make("div", "v6x-stage-backdrop");
        backdrop.innerHTML = `
            <div class="v6x-grid-plane"></div>
            <div class="v6x-horizon"></div>
            <div class="v6x-scanline"></div>
        `;

        const stageFrame = make("div", "v6x-stage-frame");
        stageFrame.appendChild(desktop);

        const contextRail = make("aside", "v6x-context-rail");
        contextRail.innerHTML = `
            <div class="v6x-context-head">
                <span>ACTIVE CONTEXT</span>
                <span class="v6x-context-live">LIVE</span>
            </div>

            <div class="v6x-context-card">
                <small>MASTER INTELLIGENCE</small>
                <strong>OMNI-JARVIS</strong>
                <p>One control plane for voice, agents, tools, research and paper trading.</p>
            </div>

            <div class="v6x-context-card">
                <small>SAFETY ENVELOPE</small>
                <strong class="v6x-safe">GOVERNED</strong>
                <p>External actions use approval gates. Broker execution remains locked.</p>
            </div>

            <div class="v6x-context-card v6x-command-hints">
                <small>QUICK ACCESS</small>
                <button type="button" data-v6x-command="Analyze the current market and explain the strongest research setup.">
                    Market scan
                </button>
                <button type="button" data-v6x-command="Show current system health and any degraded JARVIS services.">
                    System health
                </button>
                <button type="button" data-v6x-command="Show active missions and what every agent is currently doing.">
                    Mission status
                </button>
            </div>
        `;

        stage.append(backdrop, stageFrame, contextRail);

        const commandZone = make("section", "v6x-command-zone");
        commandZone.appendChild(masterConsole);

        main.append(header, stage, commandZone);
        root.append(rail, main);

        document.body.appendChild(root);

        contextRail.querySelectorAll("[data-v6x-command]").forEach((button) => {
            button.addEventListener("click", () => {
                const input = document.getElementById("commandInput");
                const execute = document.getElementById("executeButton");

                if (!input || !execute) return;

                input.value = button.dataset.v6xCommand || "";
                input.focus();
                execute.click();
            });
        });

        document.addEventListener("keydown", (event) => {
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
                event.preventDefault();
                const input = document.getElementById("commandInput");
                if (input) input.focus();
            }

            if (event.altKey) {
                const shortcuts = {
                    "1": "home",
                    "2": "chart",
                    "3": "research",
                    "4": "missions",
                    "5": "system"
                };

                if (shortcuts[event.key]) {
                    event.preventDefault();
                    window.jarvisV6SetMode(shortcuts[event.key]);
                }
            }
        });

        updateClock();
        setInterval(updateClock, 1000);

        mirrorRuntimeState();
        setInterval(mirrorRuntimeState, 750);

        let savedMode = "home";
        try {
            savedMode = localStorage.getItem("jarvisV6TerminalXMode") || "home";
        } catch (_) {}

        if (!["home", "chart", "research", "missions", "system"].includes(savedMode)) {
            savedMode = "home";
        }

        window.jarvisV6SetMode(savedMode);

        const input = document.getElementById("commandInput");
        if (input) {
            input.placeholder = "Ask JARVIS anything · Ctrl+K";
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => {
            window.setTimeout(initTerminalX, 80);
        });
    } else {
        window.setTimeout(initTerminalX, 80);
    }
})();

/* JARVIS_V6_TERMINAL_X2_JS */
(function () {
    "use strict";

    const MARKET_URL = "http://127.0.0.1:8787";

    function q(selector, root = document) {
        return root.querySelector(selector);
    }

    function qa(selector, root = document) {
        return Array.from(root.querySelectorAll(selector));
    }

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function sendCommand(text) {
        const input = document.getElementById("commandInput");
        const execute = document.getElementById("executeButton");

        if (!input || !execute) return;

        input.value = text;
        input.focus();
        execute.click();
    }

    function buildHome(frame) {
        let home = document.getElementById("v6x2-home");
        if (home) return home;

        home = el("section", "v6x2-home");
        home.id = "v6x2-home";

        home.innerHTML = `
            <div class="v6x2-home-field">
                <div class="v6x2-core-wrap">
                    <div class="v6x2-orbit orbit-a"></div>
                    <div class="v6x2-orbit orbit-b"></div>
                    <div class="v6x2-orbit orbit-c"></div>
                    <div class="v6x2-orbit orbit-d"></div>

                    <div class="v6x2-core">
                        <span class="v6x2-core-j">J</span>
                        <span class="v6x2-core-state">ACTIVE</span>
                    </div>

                    <div class="v6x2-node node-1"></div>
                    <div class="v6x2-node node-2"></div>
                    <div class="v6x2-node node-3"></div>
                    <div class="v6x2-node node-4"></div>
                </div>
            </div>

            <div class="v6x2-home-content">
                <div class="v6x2-kicker">
                    JARVIS · UNIFIED AUTONOMOUS INTELLIGENCE
                </div>

                <h1>
                    Command the
                    <span>whole system.</span>
                </h1>

                <p class="v6x2-lead">
                    One interface for research, coding, computer control,
                    missions, memory and governed market intelligence.
                </p>

                <div class="v6x2-primary-actions">
                    <button
                        type="button"
                        data-x2-command="Show me what needs my attention right now across JARVIS."
                    >
                        <span>01</span>
                        Brief me
                    </button>

                    <button
                        type="button"
                        data-x2-mode="market"
                    >
                        <span>02</span>
                        Open market intelligence
                    </button>

                    <button
                        type="button"
                        data-x2-mode="missions"
                    >
                        <span>03</span>
                        Mission control
                    </button>
                </div>

                <div class="v6x2-system-grid">
                    <article>
                        <small>ORCHESTRATION</small>
                        <strong id="v6x2-agent-count">— agents</strong>
                        <p>Capability-routed specialist mesh</p>
                    </article>

                    <article>
                        <small>ACTIVE ROUTE</small>
                        <strong id="v6x2-route">MASTER</strong>
                        <p>Dynamic intent routing</p>
                    </article>

                    <article>
                        <small>MEMORY</small>
                        <strong>HYBRID</strong>
                        <p>Scoped persistent context</p>
                    </article>

                    <article>
                        <small>TRADING</small>
                        <strong class="safe">PAPER / SHADOW</strong>
                        <p>Live broker execution locked</p>
                    </article>
                </div>
            </div>

            <div class="v6x2-edge-data">
                <div>
                    <small>CORE</small>
                    <strong id="v6x2-core-status">READY</strong>
                </div>
                <div>
                    <small>VOICE</small>
                    <strong>ONLINE</strong>
                </div>
                <div>
                    <small>CONTROL</small>
                    <strong>GOVERNED</strong>
                </div>
            </div>
        `;

        frame.appendChild(home);

        qa("[data-x2-command]", home).forEach((button) => {
            button.addEventListener("click", () => {
                sendCommand(button.dataset.x2Command || "");
            });
        });

        qa("[data-x2-mode]", home).forEach((button) => {
            button.addEventListener("click", () => {
                if (window.jarvisV6SetMode) {
                    window.jarvisV6SetMode(button.dataset.x2Mode);
                }
            });
        });

        return home;
    }

    function buildMarket(frame) {
        let market = document.getElementById("v6x2-market");
        if (market) return market;

        market = el("section", "v6x2-market");
        market.id = "v6x2-market";

        market.innerHTML = `
            <div class="v6x2-market-bar">
                <div class="v6x2-market-title">
                    <span class="v6x2-live-dot"></span>
                    <div>
                        <small>JARVIS QUANT CORE</small>
                        <strong>MARKET INTELLIGENCE</strong>
                    </div>
                </div>

                <div class="v6x2-market-status">
                    <span id="v6x2-market-state">CONNECTING · 8787</span>

                    <button type="button" id="v6x2-market-reload">
                        RELOAD
                    </button>

                    <button type="button" id="v6x2-market-external">
                        OPEN FULL ↗
                    </button>
                </div>
            </div>

            <div class="v6x2-market-frame-wrap">
                <iframe
                    id="v6x2-market-frame"
                    title="JARVIS Quant Trading Intelligence"
                    loading="eager"
                    referrerpolicy="no-referrer"
                ></iframe>

                <div class="v6x2-market-loading" id="v6x2-market-loading">
                    <div class="v6x2-loader-core">J</div>
                    <strong>CONNECTING TO QUANT CORE</strong>
                    <small>127.0.0.1:8787</small>
                </div>
            </div>
        `;

        frame.appendChild(market);

        const iframe = q("#v6x2-market-frame", market);
        const state = q("#v6x2-market-state", market);
        const loading = q("#v6x2-market-loading", market);

        function loadMarket(force = false) {
            if (!iframe) return;

            if (force || !iframe.src) {
                state.textContent = "CONNECTING · 8787";
                loading.classList.remove("hidden");

                iframe.src =
                    MARKET_URL
                    + "/?jarvis_embed=1&v="
                    + Date.now();
            }
        }

        iframe.addEventListener("load", () => {
            state.textContent = "QUANT CORE · CONNECTED";
            loading.classList.add("hidden");
        });

        q("#v6x2-market-reload", market).addEventListener("click", () => {
            loadMarket(true);
        });

        q("#v6x2-market-external", market).addEventListener("click", () => {
            window.open(MARKET_URL, "_blank", "noopener");
        });

        market._jarvisLoadMarket = loadMarket;

        return market;
    }

    function updateHomeTelemetry() {
        const agents = document.getElementById("agentCount");
        const route = document.getElementById("activeRoute");
        const master = document.getElementById("masterState");

        const a = document.getElementById("v6x2-agent-count");
        const r = document.getElementById("v6x2-route");
        const c = document.getElementById("v6x2-core-status");

        if (a && agents) {
            const value = (agents.textContent || "—").trim();
            a.textContent = value + " agents";
        }

        if (r && route) {
            r.textContent = (route.textContent || "MASTER").trim();
        }

        if (c && master) {
            c.textContent = (master.textContent || "READY").trim();
        }
    }

    function updateX2Header(mode) {
        const title = document.getElementById("v6x-mode-title");
        const sub = document.getElementById("v6x-mode-sub");

        const values = {
            home: [
                "COMMAND NEXUS",
                "Unified autonomous intelligence"
            ],
            market: [
                "MARKET INTELLIGENCE",
                "Embedded JARVIS Quant Core · 8787"
            ],
            research: [
                "INTELLIGENCE",
                "Research · evidence · synthesis"
            ],
            missions: [
                "MISSION CONTROL",
                "Agent orchestration · execution trace"
            ],
            system: [
                "SYSTEM CORE",
                "Runtime health · safeguards"
            ]
        };

        const value = values[mode] || values.home;

        if (title) title.textContent = value[0];
        if (sub) sub.textContent = value[1];
    }

    function setRail(mode) {
        qa(".v6x-rail-button").forEach((button) => {
            const buttonMode = button.dataset.mode;
            const active =
                buttonMode === mode
                || (mode === "market" && buttonMode === "chart");

            button.classList.toggle("active", active);
        });
    }

    function initX2() {
        const root = document.getElementById("v6x-root");
        const frame = q(".v6x-stage-frame");
        const desktop = document.getElementById("desktop");

        if (!root || !frame || !desktop) {
            console.error(
                "JARVIS V6 Terminal X2: Terminal X shell not found."
            );
            return;
        }

        if (document.body.classList.contains("v6x2-active")) {
            return;
        }

        document.body.classList.add("v6x2-active");

        const home = buildHome(frame);
        const market = buildMarket(frame);

        const oldSetMode = window.jarvisV6SetMode;

        window.jarvisV6SetMode = function (requestedMode) {
            const mode =
                requestedMode === "chart"
                ? "market"
                : requestedMode;

            home.classList.remove("visible");
            market.classList.remove("visible");
            desktop.classList.remove("v6x2-visible");

            if (mode === "home") {
                home.classList.add("visible");
                document.body.dataset.v6xMode = "home";
                updateX2Header("home");
                setRail("home");
            }
            else if (mode === "market") {
                market.classList.add("visible");
                document.body.dataset.v6xMode = "market";
                updateX2Header("market");
                setRail("market");

                if (market._jarvisLoadMarket) {
                    market._jarvisLoadMarket(false);
                }
            }
            else {
                desktop.classList.add("v6x2-visible");

                if (typeof oldSetMode === "function") {
                    oldSetMode(mode);
                }

                document.body.dataset.v6xMode = mode;
                updateX2Header(mode);
                setRail(mode);
            }

            try {
                localStorage.setItem(
                    "jarvisV6TerminalX2Mode",
                    mode
                );
            } catch (_) {}
        };

        // Replace the QUANT rail behavior with the integrated market workspace.
        const quant = q('.v6x-rail-button[data-mode="trading"]');
        if (quant) {
            const replacement = quant.cloneNode(true);
            replacement.dataset.mode = "market";
            replacement.title = "QUANT CORE";
            replacement.addEventListener("click", () => {
                window.jarvisV6SetMode("market");
            });
            quant.replaceWith(replacement);
        }

        updateHomeTelemetry();
        window.setInterval(updateHomeTelemetry, 700);

        let initial = "home";

        try {
            initial =
                localStorage.getItem("jarvisV6TerminalX2Mode")
                || "home";
        } catch (_) {}

        if (
            ![
                "home",
                "market",
                "research",
                "missions",
                "system"
            ].includes(initial)
        ) {
            initial = "home";
        }

        window.jarvisV6SetMode(initial);
    }

    function start() {
        // Terminal X mounts shortly after DOMContentLoaded.
        // Retry rather than depending on a brittle fixed timing assumption.
        let attempts = 0;

        const timer = window.setInterval(() => {
            attempts += 1;

            if (
                document.getElementById("v6x-root")
                && q(".v6x-stage-frame")
            ) {
                window.clearInterval(timer);
                initX2();
                return;
            }

            if (attempts >= 40) {
                window.clearInterval(timer);
                console.error(
                    "JARVIS V6 Terminal X2 could not find Terminal X shell."
                );
            }
        }, 100);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
