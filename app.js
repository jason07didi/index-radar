let marketData = null;

let currentIndex = "sse50";

let marketChart = null;


/* =========================================================
   Utils
   ========================================================= */

function $(id) {

    return document.getElementById(id);

}


function formatNumber(value) {

    if (
        value === null ||
        value === undefined ||
        Number.isNaN(Number(value))
    ) {

        return "--";

    }


    return Number(value).toLocaleString(

        "zh-CN",

        {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }

    );

}


function clamp(
    value,
    min,
    max
) {

    return Math.max(
        min,
        Math.min(max, value)
    );

}


/* =========================================================
   Load market data
   ========================================================= */

async function loadMarketData() {

    try {

        const response = await fetch(

            `data/market.json?t=${Date.now()}`,

            {
                cache: "no-store"
            }

        );


        if (!response.ok) {

            throw new Error(
                "market.json 加载失败"
            );

        }


        marketData =
            await response.json();


        $("updatedAt").textContent =
            marketData.updated_at || "--";


        renderIndex();


    } catch (error) {

        console.error(
            "加载市场数据失败：",
            error
        );


        $("marketSummary").textContent =
            "市场数据加载失败，请稍后刷新页面。";

    }

}


/* =========================================================
   Current index
   ========================================================= */

function getCurrentData() {

    if (!marketData) {

        return null;

    }


    return marketData.indices[
        currentIndex
    ];

}


/* =========================================================
   State style
   ========================================================= */

function setStateStyle(
    element,
    state
) {

    element.className =
        "market-state";


    if (state === "强势") {

        element.classList.add(
            "state-strong"
        );


    } else if (
        state === "偏强"
    ) {

        element.classList.add(
            "state-positive"
        );


    } else if (
        state === "中性"
    ) {

        element.classList.add(
            "state-neutral"
        );


    } else {

        element.classList.add(
            "state-weak"
        );

    }

}


/* =========================================================
   Market summary
   ========================================================= */

function buildMarketSummary(data) {

    const score =
        Number(data.market_score);

    const close =
        Number(data.close);

    const ma20 =
        Number(data.ma20);

    const ma60 =
        Number(data.ma60);


    let text = "";


    if (score >= 80) {

        text =
            "中长期技术结构保持强势，价格与主要趋势指标整体处于较积极状态。";


    } else if (
        score >= 65
    ) {

        text =
            "当前市场结构整体偏强，但短期动能仍需要进一步确认。";


    } else if (
        score >= 45
    ) {

        text =
            "目前多空信号交错，市场更接近震荡或方向选择阶段。";


    } else if (
        score >= 30
    ) {

        text =
            "技术结构偏弱，部分指标尚未形成一致的修复信号。";


    } else {

        text =
            "当前技术结构明显偏弱，趋势修复仍需要更多确认。";

    }


    if (
        close < ma20 &&
        close < ma60
    ) {

        text +=
            " 当前收盘同时位于 MA20 与 MA60 下方。";


    } else if (
        close > ma20 &&
        close > ma60
    ) {

        text +=
            " 当前收盘位于 MA20 与 MA60 上方。";


    } else if (
        close > ma20 &&
        close < ma60
    ) {

        text +=
            " 短期结构有所修复，但中期趋势尚未完全确认。";


    } else {

        text +=
            " 当前短期与中期趋势信号存在分化。";

    }


    return text;

}


/* =========================================================
   Local storage
   ========================================================= */

function storageKey(field) {

    return (
        "indexRadar_" +
        currentIndex +
        "_" +
        field
    );

}


function loadUserSettings() {

    const position =
        localStorage.getItem(
            storageKey("position")
        );


    const profit =
        localStorage.getItem(
            storageKey("profit")
        );


    const risk =
        localStorage.getItem(
            storageKey("risk")
        );


    $("positionInput").value =
        position !== null
            ? position
            : 50;


    $("profitInput").value =
        profit !== null
            ? profit
            : 0;


    $("riskSelect").value =
        risk || "balanced";

}


function saveUserSettings() {

    localStorage.setItem(
        storageKey("position"),
        $("positionInput").value
    );


    localStorage.setItem(
        storageKey("profit"),
        $("profitInput").value
    );


    localStorage.setItem(
        storageKey("risk"),
        $("riskSelect").value
    );

}


/* =========================================================
   Target position
   ========================================================= */

function getBaseTargetPosition(
    score,
    risk
) {

    let ranges;


    if (
        risk === "conservative"
    ) {

        ranges = {

            strong: [55, 70],

            positive: [40, 55],

            neutral: [25, 40],

            weak: [10, 25],

            veryWeak: [0, 15]

        };


    } else if (
        risk === "aggressive"
    ) {

        ranges = {

            strong: [80, 95],

            positive: [65, 80],

            neutral: [45, 65],

            weak: [25, 45],

            veryWeak: [10, 30]

        };


    } else {

        ranges = {

            strong: [70, 85],

            positive: [55, 70],

            neutral: [35, 55],

            weak: [20, 35],

            veryWeak: [5, 20]

        };

    }


    if (score >= 80) {

        return ranges.strong;

    }


    if (score >= 65) {

        return ranges.positive;

    }


    if (score >= 45) {

        return ranges.neutral;

    }


    if (score >= 30) {

        return ranges.weak;

    }


    return ranges.veryWeak;

}


/* =========================================================
   User strategy
   ========================================================= */

function calculateUserStrategy(data) {

    let position =
        Number(
            $("positionInput").value
        );


    let profit =
        Number(
            $("profitInput").value
        );


    position = clamp(

        Number.isFinite(position)
            ? position
            : 0,

        0,

        100

    );


    profit =
        Number.isFinite(profit)
            ? profit
            : 0;


    const risk =
        $("riskSelect").value;


    const score =
        Number(
            data.market_score
        );


    let [
        targetLow,
        targetHigh
    ] =
        getBaseTargetPosition(
            score,
            risk
        );


    if (
        profit >= 20 &&
        data.rsi14 >= 70
    ) {

        targetLow -= 10;

        targetHigh -= 10;

    }


    if (
        profit <= -10 &&
        score < 45
    ) {

        targetLow -= 5;

        targetHigh -= 5;

    }


    targetLow =
        clamp(
            targetLow,
            0,
            100
        );


    targetHigh =
        clamp(
            targetHigh,
            0,
            100
        );


    let action;

    let text;


    if (
        position <
        targetLow - 10
    ) {

        action =
            "等待后分批增加";


        text =
            `当前仓位 ${position.toFixed(0)}%，` +
            `明显低于当前市场状态对应的参考区间。` +
            `若价格在关键支撑附近企稳，并重新获得短期趋势确认，` +
            `可考虑分批向 ${targetLow}%–${targetHigh}% 区间调整。`;


    } else if (
        position < targetLow
    ) {

        action =
            "小幅增加";


        text =
            "当前仓位略低于参考区间。" +
            "不建议一次性追价，可等待短期趋势确认后再逐步调整。";


    } else if (
        position <= targetHigh
    ) {

        action =
            "维持仓位";


        text =
            `当前 ${position.toFixed(0)}% 的仓位已经处于 ` +
            `${targetLow}%–${targetHigh}% 的参考区间内。` +
            "现阶段更适合观察市场结构变化，而不是频繁调整。";


    } else if (
        position <=
        targetHigh + 10
    ) {

        action =
            "适度降低";


        text =
            "当前仓位略高于该市场状态对应的参考区间。" +
            "可结合关键压力位、短期均线及已有盈利情况，" +
            "适度降低风险暴露。";


    } else {

        action =
            "优先控制仓位";


        text =
            "当前仓位明显高于技术状态对应的参考区间。" +
            "如果趋势没有重新强化，应优先关注风险控制，" +
            "而不是继续扩大仓位。";

    }


    if (
        profit >= 20
    ) {

        text +=
            ` 当前已有 ${profit.toFixed(1)}% 浮盈，` +
            "应更加关注盈利回撤风险。";


    } else if (
        profit >= 8
    ) {

        text +=
            " 当前已有一定浮盈，可将保护已有收益作为辅助考虑。";


    } else if (
        profit <= -10
    ) {

        text +=
            " 当前处于较明显浮亏状态，策略判断不应以“回本”为主要依据。";

    }


    return {

        action,

        text,

        targetLow,

        targetHigh,

        position,

        profit,

        risk

    };

}


/* =========================================================
   Render strategy
   ========================================================= */

function renderStrategy(data) {

    const result =
        calculateUserStrategy(data);


    $("strategyAction").textContent =
        result.action;


    $("targetPosition").textContent =
        `${result.targetLow}%–${result.targetHigh}%`;


    $("strategyText").textContent =
        result.text;


    const tags = [

        `市场 ${data.market_state}`,

        `评分 ${data.market_score}`,

        `仓位 ${result.position.toFixed(0)}%`,

        `收益 ${
            result.profit >= 0
                ? "+"
                : ""
        }${result.profit.toFixed(1)}%`

    ];


    $("strategyTags").innerHTML =

        tags.map(

            item =>

                `<span class="strategy-tag">
                    ${item}
                </span>`

        ).join("");

}


/* =========================================================
   Reasons
   ========================================================= */

function renderReasons(data) {

    const reasons =
        data.market_reasons || [];


    $("marketReasons").innerHTML =

        reasons.map(

            item => `

                <div class="reason-item">

                    <span class="reason-dot"></span>

                    <span>
                        ${item}
                    </span>

                </div>

            `

        ).join("");

}


/* =========================================================
   Scenarios
   ========================================================= */

function renderScenarios(data) {

    const scenarios = [

        {

            title:
                `重新站上 MA20 ${formatNumber(data.ma20)}`,

            text:
                "若收盘重新站稳 MA20，说明短期趋势有所修复，可继续观察 MA5 与 MA20 是否进一步形成多头排列。"

        },

        {

            title:
                `测试 MA60 ${formatNumber(data.ma60)}`,

            text:
                "MA60 用于观察中期趋势。有效站稳其上方通常意味着中期结构进一步改善；持续受阻则说明趋势修复仍不充分。"

        },

        {

            title:
                `跌破近20日低点 ${formatNumber(data.low20)}`,

            text:
                "若日线进一步跌破近期低点，说明弱势结构可能继续扩展，此时应提高对风险暴露的关注。"

        },

        {

            title:
                `突破近20日高点 ${formatNumber(data.high20)}`,

            text:
                "若价格有效突破近期高点并伴随均线改善，可视为趋势进一步强化的重要确认条件之一。"

        }

    ];


    $("scenarioList").innerHTML =

        scenarios.map(

            item => `

                <div class="scenario-card">

                    <strong>
                        ${item.title}
                    </strong>

                    <p>
                        ${item.text}
                    </p>

                </div>

            `

        ).join("");

}


/* =========================================================
   Refined chart
   ========================================================= */

function renderChart(data) {

    const history =
        data.history || [];


    const labels =
        history.map(

            item =>
                item.date.slice(5)

        );


    /*
       核心视觉逻辑：

       收盘   石墨黑
       MA5    雾霾蓝灰
       MA20   暖灰棕
       MA60   灰紫

       全部降低饱和度
    */

    const datasets = [

        {

            label: "收盘",

            data:
                history.map(
                    item =>
                        item.close
                ),

            borderColor:
                "#1D1D1F",

            backgroundColor:
                "#1D1D1F",

            borderWidth: 2.35,

            pointRadius: 0,

            pointHoverRadius: 3.5,

            pointHoverBackgroundColor:
                "#1D1D1F",

            pointHoverBorderColor:
                "#FFFFFF",

            pointHoverBorderWidth: 2,

            tension: 0.24

        },


        {

            label: "MA5",

            data:
                history.map(
                    item =>
                        item.ma5
                ),

            borderColor:
                "#6F8FA8",

            backgroundColor:
                "#6F8FA8",

            borderWidth: 1.55,

            pointRadius: 0,

            pointHoverRadius: 3,

            pointHoverBackgroundColor:
                "#6F8FA8",

            pointHoverBorderColor:
                "#FFFFFF",

            pointHoverBorderWidth: 2,

            tension: 0.24

        },


        {

            label: "MA20",

            data:
                history.map(
                    item =>
                        item.ma20
                ),

            borderColor:
                "#A58B72",

            backgroundColor:
                "#A58B72",

            borderWidth: 1.45,

            pointRadius: 0,

            pointHoverRadius: 3,

            pointHoverBackgroundColor:
                "#A58B72",

            pointHoverBorderColor:
                "#FFFFFF",

            pointHoverBorderWidth: 2,

            tension: 0.24

        },


        {

            label: "MA60",

            data:
                history.map(
                    item =>
                        item.ma60
                ),

            borderColor:
                "#858292",

            backgroundColor:
                "#858292",

            borderWidth: 1.35,

            pointRadius: 0,

            pointHoverRadius: 3,

            pointHoverBackgroundColor:
                "#858292",

            pointHoverBorderColor:
                "#FFFFFF",

            pointHoverBorderWidth: 2,

            tension: 0.24

        }

    ];


    if (marketChart) {

        marketChart.destroy();

    }


    const ctx =
        $("marketChart")
            .getContext("2d");


    marketChart =
        new Chart(

            ctx,

            {

                type: "line",


                data: {

                    labels,

                    datasets

                },


                options: {

                    responsive: true,

                    maintainAspectRatio:
                        false,


                    animation: {

                        duration: 420,

                        easing:
                            "easeOutQuart"

                    },


                    interaction: {

                        mode: "index",

                        intersect: false

                    },


                    layout: {

                        padding: {

                            top: 4,

                            left: 3,

                            right: 8,

                            bottom: 1

                        }

                    },


                    plugins: {

                        legend: {

                            position: "top",

                            align: "start",

                            labels: {

                                usePointStyle:
                                    true,

                                pointStyle:
                                    "line",

                                boxWidth: 23,

                                boxHeight: 3,

                                padding: 19,

                                color:
                                    "#7A7A80",

                                font: {

                                    size: 11,

                                    weight: 500

                                }

                            }

                        },


                        tooltip: {

                            enabled: true,

                            backgroundColor:
                                "rgba(37,37,39,0.94)",

                            titleColor:
                                "#FFFFFF",

                            bodyColor:
                                "rgba(255,255,255,0.76)",

                            borderWidth: 0,

                            cornerRadius: 14,

                            padding: 13,

                            boxPadding: 5,

                            usePointStyle:
                                true,

                            displayColors:
                                true,


                            titleFont: {

                                size: 11,

                                weight: 600

                            },


                            bodyFont: {

                                size: 11

                            },


                            callbacks: {

                                label:
                                    function(context) {

                                        const value =
                                            context.parsed.y;


                                        return (
                                            context.dataset.label +
                                            "   " +
                                            Number(value)
                                                .toLocaleString(
                                                    "zh-CN",
                                                    {
                                                        minimumFractionDigits: 2,
                                                        maximumFractionDigits: 2
                                                    }
                                                )
                                        );

                                    }

                            }

                        }

                    },


                    scales: {

                        x: {

                            border: {

                                display: false

                            },


                            grid: {

                                display: false

                            },


                            ticks: {

                                color:
                                    "#9A9A9F",

                                maxTicksLimit:
                                    7,

                                maxRotation:
                                    0,

                                padding:
                                    8,

                                font: {

                                    size: 10

                                }

                            }

                        },


                        y: {

                            border: {

                                display: false

                            },


                            grid: {

                                color:
                                    "rgba(60,60,67,0.055)",

                                lineWidth:
                                    1

                            },


                            ticks: {

                                color:
                                    "#9A9A9F",

                                padding:
                                    10,

                                font: {

                                    size: 10

                                },

                                callback:
                                    function(value) {

                                        return Number(
                                            value
                                        ).toLocaleString();

                                    }

                            }

                        }

                    }

                }

            }

        );

}


/* =========================================================
   Render current index
   ========================================================= */

function renderIndex() {

    const data =
        getCurrentData();


    if (!data) {

        return;

    }


    if (data.error) {

        $("marketSummary").textContent =
            `数据获取失败：${data.error}`;

        return;

    }


    loadUserSettings();


    $("indexName").textContent =
        data.name;


    $("indexSymbol").textContent =
        `${data.symbol} · ${data.date} · ${data.source}`;


    $("closePrice").textContent =
        formatNumber(
            data.close
        );


    const changeElement =
        $("changePct");


    changeElement.textContent =

        `${data.change_pct >= 0 ? "+" : ""}` +

        `${Number(data.change_pct).toFixed(2)}%`;


    changeElement.className =
        "change " +

        (
            data.change_pct > 0

                ? "positive"

                : data.change_pct < 0

                    ? "negative"

                    : "neutral"
        );


    $("marketScore").textContent =
        data.market_score;


    $("scoreProgress").style.width =
        "0%";


    requestAnimationFrame(

        () => {

            $("scoreProgress").style.width =
                `${data.market_score}%`;

        }

    );


    $("marketState").textContent =
        data.market_state;


    setStateStyle(

        $("marketState"),

        data.market_state

    );


    $("marketSummary").textContent =
        buildMarketSummary(
            data
        );


    $("ma5").textContent =
        formatNumber(
            data.ma5
        );


    $("ma20").textContent =
        formatNumber(
            data.ma20
        );


    $("ma60").textContent =
        formatNumber(
            data.ma60
        );


    $("rsi14").textContent =
        formatNumber(
            data.rsi14
        );


    $("macdHist").textContent =
        formatNumber(
            data.macd_hist
        );


    $("bollMid").textContent =
        formatNumber(
            data.boll_mid
        );


    $("support1").textContent =
        formatNumber(
            data.boll_lower
        );


    $("support2").textContent =
        formatNumber(
            data.low20
        );


    $("pressure1").textContent =
        formatNumber(
            data.ma20
        );


    $("pressure2").textContent =
        formatNumber(
            data.high20
        );


    renderStrategy(data);

    renderReasons(data);

    renderScenarios(data);

    renderChart(data);

}


/* =========================================================
   Index switching
   ========================================================= */

document
    .querySelectorAll(
        ".index-tab"
    )
    .forEach(

        button => {

            button.addEventListener(

                "click",

                () => {

                    document
                        .querySelectorAll(
                            ".index-tab"
                        )
                        .forEach(

                            item =>
                                item.classList.remove(
                                    "active"
                                )

                        );


                    button.classList.add(
                        "active"
                    );


                    currentIndex =
                        button.dataset.index;


                    renderIndex();

                }

            );

        }

    );


/* =========================================================
   User input
   ========================================================= */

[
    "positionInput",
    "profitInput",
    "riskSelect"
]
.forEach(

    id => {

        $(id).addEventListener(

            "input",

            () => {

                saveUserSettings();


                const data =
                    getCurrentData();


                if (data) {

                    renderStrategy(data);

                }

            }

        );


        $(id).addEventListener(

            "change",

            () => {

                saveUserSettings();


                const data =
                    getCurrentData();


                if (data) {

                    renderStrategy(data);

                }

            }

        );

    }

);


/* =========================================================
   Init
   ========================================================= */

loadMarketData();


/* =========================================================
   Refresh market.json every 5 minutes
   ========================================================= */

setInterval(

    loadMarketData,

    5 * 60 * 1000

);
