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

        setGeometry(
            "chart",
            "1%",
            "2%",
            "31%",
            "57%"
        );

        setGeometry(
            "core",
            "33%",
            "3%",
            "34%",
            "49%"
        );

        setGeometry(
            "missions",
            "68%",
            "2%",
            "31%",
            "46%"
        );

        setGeometry(
            "paper",
            "1%",
            "61%",
            "31%",
            "37%"
        );

        setGeometry(
            "quant",
            "33%",
            "54%",
            "34%",
            "44%"
        );

        setGeometry(
            "research",
            "68%",
            "50%",
            "31%",
            "48%"
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
        "jarvisV31Workspace",
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
                    "jarvisV31Workspace"
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
    forced = null
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
                                text
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
            agents.length;


        renderAgentMesh(
            agents
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
        of agents.slice(
            0,
            24
        )
    ) {

        const card =
            document.createElement(
                "div"
            );


        card.className =
            "agentCard";

        card.textContent =
            String(
                name
            ).toUpperCase();


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
        text
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


        input.value =
            value;


        input.dispatchEvent(
            new Event(
                "input",
                {
                    bubbles:
                        true,
                }
            )
        );


        execute.click();


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
                ]
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
                transcript
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
                transcript
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


