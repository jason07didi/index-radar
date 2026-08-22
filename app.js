let marketData = null;

let currentIndex = "sse50";

let marketChart = null;


const indexKeys = {
    sse50: "上证50",
    nasdaq100: "纳斯达克100",
    sp500: "标普500"
};


/* ========================================================
   工具
======================================================== */

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


function clamp(value, min, max) {
    return Math.max(
        min,
        Math.min(max, value)
    );
}


/* ========================================================
   读取数据
======================================================== */

async function loadMarketData() {

    try {

        const response = await fetch(
            `data/market.json?t=${Date.now()}`
        );

        if (!response.ok) {
            throw new Error(
                "market.json 加载失败"
            );
        }

        marketData = await response.json();

        $("updatedAt").textContent =
            marketData.updated_at || "--";

        renderIndex();

    } catch (error) {

        console.error(error);

        $("marketSummary").textContent =
            "市场数据加载失败，请稍后刷新页面。";
    }
}


/* ========================================================
   当前指数
======================================================== */

function getCurrentData() {

    if (!marketData) {
        return null;
    }

    return marketData.indices[
        currentIndex
    ];
}


/* ========================================================
   市场状态颜色
======================================================== */

function setStateStyle(element, state) {

    element.className =
        "market-state";

    if (state === "强势") {

        element.classList.add(
            "state-strong"
        );

    } else if (state === "偏强") {

        element.classList.add(
            "state-positive"
        );

    } else if (state === "中性") {

        element.classList.add(
            "state-neutral"
        );

    } else {

        element.classList.add(
            "state-weak"
        );
    }
}


/* ========================================================
   市场摘要
======================================================== */

function buildMarketSummary(data) {

    const score = data.market_score;

    const close = data.close;

    const ma20 = data.ma20;

    const ma60 = data.ma60;

    let text = "";


    if (score >= 80) {

        text =
            "中长期技术结构保持强势，价格位于主要趋势均线上方。";

    } else if (score >= 65) {

        text =
            "整体结构偏强，但仍需关注短期动能是否继续确认。";

    } else if (score >= 45) {

        text =
            "多空信号交错，目前更接近震荡或方向选择阶段。";

    } else if (score >= 30) {

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
            " 当前收盘同时位于MA20和MA60下方。";

    } else if (
        close > ma20 &&
        close > ma60
    ) {

        text +=
            " 当前收盘位于MA20和MA60上方。";
    }


    return text;
}


/* ========================================================
   用户资料
======================================================== */

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


/* ========================================================
   根据市场评分获得基础仓位
======================================================== */

function getBaseTargetPosition(
    score,
    risk
) {

    let ranges;


    if (risk === "conservative") {

        ranges = {
            strong: [55, 70],
            positive: [40, 55],
            neutral: [25, 40],
            weak: [10, 25],
            veryWeak: [0, 15]
        };

    } else if (risk === "aggressive") {

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


/* ========================================================
   个性化策略

   输入：
   市场评分
   当前仓位
   当前收益率
   风格

   输出：
   参考动作
======================================================== */

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
        Number(data.market_score);


    let [
        targetLow,
        targetHigh
    ] = getBaseTargetPosition(
        score,
        risk
    );


    /*
       高盈利且动能较热：
       略微降低目标仓位
    */

    if (
        profit >= 20 &&
        data.rsi14 >= 70
    ) {

        targetLow -= 10;
        targetHigh -= 10;
    }


    /*
       明显亏损 + 弱势结构：
       不因为亏损而机械加仓
    */

    if (
        profit <= -10 &&
        score < 45
    ) {

        targetLow -= 5;
        targetHigh -= 5;
    }


    targetLow =
        clamp(targetLow, 0, 100);

    targetHigh =
        clamp(targetHigh, 0, 100);


    let action;

    let text;


    if (
        position < targetLow - 10
    ) {

        action = "等待后分批增加";

        text =
            `当前仓位 ${position.toFixed(0)}%，` +
            `低于该市场状态下的参考区间。` +
            `若价格在关键支撑附近企稳，并重新获得短期均线确认，` +
            `可考虑分批向 ${targetLow}%–${targetHigh}% 区间调整。`;


    } else if (
        position < targetLow
    ) {

        action = "小幅增加";

        text =
            `当前仓位略低于参考区间。` +
            `不建议一次性追价，可等待短期趋势确认后小幅调整仓位。`;


    } else if (
        position <= targetHigh
    ) {

        action = "维持仓位";

        text =
            `当前 ${position.toFixed(0)}% 的仓位已经处于` +
            `${targetLow}%–${targetHigh}% 的参考区间内，` +
            `现阶段更适合观察市场结构变化，而不是频繁调整。`;


    } else if (
        position <= targetHigh + 10
    ) {

        action = "适度降低";

        text =
            `当前仓位高于该市场状态对应的参考区间。` +
            `可根据关键压力位、短期均线和已有盈利情况，` +
            `考虑适度降低风险暴露。`;


    } else {

        action = "优先控制仓位";

        text =
            `当前仓位明显高于技术状态对应的参考区间。` +
            `如果趋势没有重新强化，应优先关注风险控制，` +
            `而不是继续扩大仓位。`;
    }


    /*
       浮盈修正说明
    */

    if (profit >= 20) {

        text +=
            ` 当前已有 ${profit.toFixed(1)}% 浮盈，` +
            `应更加关注盈利回撤风险。`;

    } else if (profit >= 8) {

        text +=
            ` 当前已有一定浮盈，可将保护已有收益作为辅助考虑。`;

    } else if (profit <= -10) {

        text +=
            ` 当前处于较明显浮亏状态，策略判断不应以“回本”为主要依据。`;
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


/* ========================================================
   渲染策略
======================================================== */

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

        `收益 ${result.profit >= 0 ? "+" : ""}${result.profit.toFixed(1)}%`

    ];


    $("strategyTags").innerHTML =
        tags.map(
            item =>
                `<span class="strategy-tag">${item}</span>`
        ).join("");
}


/* ========================================================
   判断依据
======================================================== */

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


/* ========================================================
   情景推演
======================================================== */

function renderScenarios(data) {

    const scenarios = [

        {
            title:
                `重新站上 MA20 ${formatNumber(data.ma20)}`,

            text:
                "若收盘重新站稳MA20，说明短期趋势有所修复，可观察MA5与MA20是否进一步形成多头排列。"
        },

        {
            title:
                `测试 MA60 ${formatNumber(data.ma60)}`,

            text:
                "MA60用于观察中期趋势。有效站稳其上方通常意味着中期结构进一步改善；持续受阻则说明趋势修复仍不充分。"
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
                "若价格有效突破近期高点并伴随均线改善，可视为趋势强化的重要确认条件之一。"
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


/* ========================================================
   图表
======================================================== */

function renderChart(data) {

    const history =
        data.history || [];


    const labels =
        history.map(
            item =>
                item.date.slice(5)
        );


    const datasets = [

        {
            label: "收盘",
            data: history.map(
                item => item.close
            ),
            borderColor: "#161616",
            borderWidth: 2.4,
            pointRadius: 0,
            tension: 0.15
        },

        {
            label: "MA5",
            data: history.map(
                item => item.ma5
            ),
            borderColor: "#2869d8",
            borderWidth: 1.7,
            pointRadius: 0,
            tension: 0.15
        },

        {
            label: "MA20",
            data: history.map(
                item => item.ma20
            ),
            borderColor: "#ef8219",
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.15
        },

        {
            label: "MA60",
            data: history.map(
                item => item.ma60
            ),
            borderColor: "#7057d9",
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.15
        }

    ];


    if (marketChart) {
        marketChart.destroy();
    }


    const ctx =
        $("marketChart").getContext(
            "2d"
        );


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

                    maintainAspectRatio: false,

                    interaction: {
                        mode: "index",
                        intersect: false
                    },

                    plugins: {

                        legend: {
                            position: "top",
                            align: "start"
                        }

                    },

                    scales: {

                        x: {

                            grid: {
                                display: false
                            },

                            ticks: {
                                maxTicksLimit: 8
                            }

                        },

                        y: {

                            grid: {
                                color:
                                    "rgba(0,0,0,0.055)"
                            },

                            ticks: {
                                callback:
                                    value =>
                                        Number(value)
                                            .toLocaleString()
                            }

                        }

                    }

                }

            }
        );
}


/* ========================================================
   渲染整个指数
======================================================== */

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
        formatNumber(data.close);


    const changeElement =
        $("changePct");


    changeElement.textContent =
        `${data.change_pct >= 0 ? "+" : ""}${data.change_pct.toFixed(2)}%`;


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
        `${data.market_score}%`;


    $("marketState").textContent =
        data.market_state;


    setStateStyle(
        $("marketState"),
        data.market_state
    );


    $("marketSummary").textContent =
        buildMarketSummary(data);


    $("ma5").textContent =
        formatNumber(data.ma5);


    $("ma20").textContent =
        formatNumber(data.ma20);


    $("ma60").textContent =
        formatNumber(data.ma60);


    $("rsi14").textContent =
        formatNumber(data.rsi14);


    $("macdHist").textContent =
        formatNumber(data.macd_hist);


    $("bollMid").textContent =
        formatNumber(data.boll_mid);


    $("support1").textContent =
        formatNumber(data.boll_lower);


    $("support2").textContent =
        formatNumber(data.low20);


    $("pressure1").textContent =
        formatNumber(data.ma20);


    $("pressure2").textContent =
        formatNumber(data.high20);


    renderStrategy(data);

    renderReasons(data);

    renderScenarios(data);

    renderChart(data);
}


/* ========================================================
   指数切换
======================================================== */

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


/* ========================================================
   用户输入变化
======================================================== */

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


/* ========================================================
   启动
======================================================== */

loadMarketData();


/*
   页面打开期间每5分钟重新检查一次market.json
*/

setInterval(
    loadMarketData,
    5 * 60 * 1000
);
