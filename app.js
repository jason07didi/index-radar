/* =========================================================
   INDEX RADAR
   Frontend Strategy Engine 3.0

   核心逻辑：

   1. 长期配置吸引力
      决定是否值得增加长期资金

   2. 市场温度
      越热越谨慎，越冷越关注机会

   3. 短期技术状态
      决定加仓节奏，而非长期价值

   4. 历史相似情境
      展示未来20个交易日的历史条件频率

   5. 用户输入
      当前仓位
      当前收益
      每月基础定投
      投资风格
   ========================================================= */


/* =========================================================
   全局状态
   ========================================================= */

let marketData = null;

let currentIndex = "sse50";

let currentChartRange = 252;

let marketChart = null;


/* =========================================================
   基础工具
   ========================================================= */

function $(id) {

    return document.getElementById(id);

}


function clamp(
    value,
    min,
    max
) {

    return Math.max(
        min,
        Math.min(
            max,
            value
        )
    );

}


function safeNumber(
    value,
    fallback = 0
) {

    const number =
        Number(value);


    return Number.isFinite(number)
        ? number
        : fallback;

}


function formatNumber(
    value,
    digits = 2
) {

    if (
        value === null ||
        value === undefined ||
        Number.isNaN(
            Number(value)
        )
    ) {

        return "--";

    }


    return Number(value)
        .toLocaleString(

            "zh-CN",

            {
                minimumFractionDigits:
                    digits,

                maximumFractionDigits:
                    digits
            }

        );

}


function formatPercent(
    value,
    digits = 2
) {

    if (
        value === null ||
        value === undefined ||
        Number.isNaN(
            Number(value)
        )
    ) {

        return "--";

    }


    const number =
        Number(value);


    return (
        (
            number > 0
                ? "+"
                : ""
        )

        +

        number.toFixed(
            digits
        )

        +

        "%"
    );

}


function formatCurrency(
    value
) {

    const number =
        safeNumber(
            value,
            0
        );


    return (
        "¥" +

        Math.round(number)
            .toLocaleString(
                "zh-CN"
            )
    );

}


function setPercentBar(
    elementId,
    value
) {

    const element =
        $(elementId);


    if (!element) {

        return;

    }


    element.style.width =
        "0%";


    requestAnimationFrame(

        () => {

            element.style.width =
                `${clamp(
                    safeNumber(value),
                    0,
                    100
                )}%`;

        }

    );

}


/* =========================================================
   加载 market.json
   ========================================================= */

async function loadMarketData() {

    try {

        const response =
            await fetch(

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


        if ($("updatedAt")) {

            $("updatedAt").textContent =
                marketData.updated_at
                || "--";

        }


        renderCurrentIndex();


    } catch (error) {

        console.error(
            "市场数据加载失败：",
            error
        );


        if ($("coreConclusion")) {

            $("coreConclusion").textContent =
                "市场数据加载失败，请稍后刷新页面。";

        }

    }

}


/* =========================================================
   当前指数
   ========================================================= */

function getCurrentData() {

    if (
        !marketData ||
        !marketData.indices
    ) {

        return null;

    }


    return (
        marketData.indices[
            currentIndex
        ]

        || null
    );

}


/* =========================================================
   LocalStorage
   每个指数单独保存用户设置
   ========================================================= */

function storageKey(
    field
) {

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
            storageKey(
                "position"
            )
        );


    const profit =
        localStorage.getItem(
            storageKey(
                "profit"
            )
        );


    const investment =
        localStorage.getItem(
            storageKey(
                "baseInvestment"
            )
        );


    const risk =
        localStorage.getItem(
            storageKey(
                "risk"
            )
        );


    if ($("positionInput")) {

        $("positionInput").value =

            position !== null

                ? position

                : 50;

    }


    if ($("profitInput")) {

        $("profitInput").value =

            profit !== null

                ? profit

                : 0;

    }


    if ($("baseInvestmentInput")) {

        $("baseInvestmentInput").value =

            investment !== null

                ? investment

                : 3000;

    }


    if ($("riskSelect")) {

        $("riskSelect").value =
            risk
            || "balanced";

    }

}


function saveUserSettings() {

    localStorage.setItem(

        storageKey(
            "position"
        ),

        $("positionInput").value

    );


    localStorage.setItem(

        storageKey(
            "profit"
        ),

        $("profitInput").value

    );


    localStorage.setItem(

        storageKey(
            "baseInvestment"
        ),

        $("baseInvestmentInput").value

    );


    localStorage.setItem(

        storageKey(
            "risk"
        ),

        $("riskSelect").value

    );

}


/* =========================================================
   长期配置状态样式
   ========================================================= */

function setAllocationBadge(
    state
) {

    const element =
        $("allocationState");


    if (!element) {

        return;

    }


    element.className =
        "allocation-badge";


    if (
        state === "高吸引力"
    ) {

        element.classList.add(
            "allocation-high"
        );


    } else if (
        state === "较高吸引力"
    ) {

        element.classList.add(
            "allocation-good"
        );


    } else if (
        state === "中性"
    ) {

        element.classList.add(
            "allocation-neutral"
        );


    } else {

        element.classList.add(
            "allocation-low"
        );

    }


    element.textContent =
        state || "--";

}


/* =========================================================
   当前一句话结论
   ========================================================= */

function buildCoreConclusion(
    data
) {

    const allocation =
        safeNumber(
            data.allocation_score,
            50
        );


    const temperature =
        safeNumber(
            data.market_temperature,
            50
        );


    const technical =
        data.technical_state
        || "中性";


    if (
        allocation >= 70 &&
        temperature <= 40
    ) {

        if (
            technical === "弱势" ||
            technical === "偏弱"
        ) {

            return (
                "长期价格条件已经明显改善，但短期走势仍偏弱。" +
                "基础定投可以继续，额外资金更适合分批保留，等待企稳或趋势修复后再逐步投入。"
            );

        }


        return (
            "长期配置吸引力较高，市场温度也不高，" +
            "且技术结构开始具备修复条件。" +
            "当前更适合采用分批增加配置，而不是一次性追价。"
        );

    }


    if (
        allocation >= 55 &&
        temperature <= 50
    ) {

        return (
            "当前长期价格处于相对合理区域，" +
            "适合维持基础定投，并在明显回撤或技术企稳时进行适度增强。"
        );

    }


    if (
        allocation <= 30 &&
        temperature >= 70
    ) {

        return (
            "当前价格偏热，长期配置吸引力较低。" +
            "不适合因为上涨而继续追高；若仓位已经较高且积累较大浮盈，" +
            "更应考虑降低新增投入或进行适度再平衡。"
        );

    }


    if (
        temperature >= 80
    ) {

        return (
            "当前市场热度已经较高。" +
            "即使短期趋势仍然强势，也应降低追涨冲动，" +
            "把更多资金留给未来回撤。"
        );

    }


    if (
        technical === "弱势"
        &&
        allocation < 55
    ) {

        return (
            "长期配置吸引力暂未明显提升，同时短期技术结构偏弱。" +
            "现阶段更适合保持基础定投，避免因为短期下跌而机械重仓补仓。"
        );

    }


    return (
        "当前长期价格与市场热度总体处于中间区域。" +
        "更适合维持既定定投计划，等待价格显著偏离长期均衡后再调整投入节奏。"
    );

}


/* =========================================================
   定投基础倍率
   ========================================================= */

function getAllocationMultiplier(
    score
) {

    if (score >= 85) {

        return 1.80;

    }


    if (score >= 70) {

        return 1.55;

    }


    if (score >= 55) {

        return 1.25;

    }


    if (score >= 40) {

        return 1.00;

    }


    if (score >= 25) {

        return 0.75;

    }


    return 0.50;

}


/* =========================================================
   投资风格调节
   ========================================================= */

function getRiskAdjustment(
    risk
) {

    if (
        risk === "conservative"
    ) {

        return -0.15;

    }


    if (
        risk === "aggressive"
    ) {

        return 0.15;

    }


    return 0;

}


/* =========================================================
   个性化定投 / 加减仓策略
   ========================================================= */

function calculateInvestmentStrategy(
    data
) {

    const position =
        clamp(

            safeNumber(
                $("positionInput").value,
                50
            ),

            0,

            100

        );


    const profit =
        safeNumber(
            $("profitInput").value,
            0
        );


    const baseInvestment =
        Math.max(

            0,

            safeNumber(
                $("baseInvestmentInput").value,
                3000
            )

        );


    const risk =
        $("riskSelect").value;


    const allocation =
        safeNumber(
            data.allocation_score,
            50
        );


    const temperature =
        safeNumber(
            data.market_temperature,
            50
        );


    const technical =
        data.technical_state
        || "中性";


    let multiplier =
        getAllocationMultiplier(
            allocation
        );


    /* =====================================================
       投资风格
       ===================================================== */

    multiplier +=
        getRiskAdjustment(
            risk
        );


    /* =====================================================
       市场温度调节

       冷：
       长期资金略增加

       热：
       降低新增投入
       ===================================================== */

    if (
        temperature <= 20
    ) {

        multiplier += 0.30;


    } else if (
        temperature <= 35
    ) {

        multiplier += 0.15;


    } else if (
        temperature >= 85
    ) {

        multiplier -= 0.55;


    } else if (
        temperature >= 70
    ) {

        multiplier -= 0.30;

    }


    /* =====================================================
       当前仓位调节
       ===================================================== */

    if (
        position >= 90
    ) {

        multiplier -= 0.45;


    } else if (
        position >= 75
    ) {

        multiplier -= 0.25;


    } else if (
        position <= 30 &&
        allocation >= 65
    ) {

        multiplier += 0.10;

    }


    /* =====================================================
       浮盈 + 热度

       已经涨了很多，
       且市场偏热时不继续追
       ===================================================== */

    if (
        profit >= 20 &&
        temperature >= 65
    ) {

        multiplier -= 0.20;

    }


    /* =====================================================
       技术确认

       注意：
       技术弱并不等于长期卖出。

       只是限制“额外加仓”的速度。
       ===================================================== */

    if (
        allocation >= 65 &&
        (
            technical === "弱势" ||
            technical === "偏弱"
        )
    ) {

        multiplier =
            Math.min(
                multiplier,
                1.25
            );

    }


    if (
        allocation >= 60 &&
        (
            technical === "偏强" ||
            technical === "强势"
        )
    ) {

        multiplier += 0.10;

    }


    /* =====================================================
       美国宏观环境辅助
       ===================================================== */

    const macro =
        marketData
        ? marketData.macro
        : null;


    if (
        currentIndex !== "sse50" &&
        macro
    ) {

        const vix =
            macro.vix;


        const us10y =
            macro.us10y;


        /* ================================================
           恐慌 + 长期配置吸引力较高
           略提高逆向配置权重
           ================================================ */

        if (
            vix &&
            !vix.error &&
            safeNumber(
                vix.value
            ) >= 30 &&
            allocation >= 55
        ) {

            multiplier += 0.10;

        }


        /* ================================================
           利率快速上行
           对成长型纳指适度降权
           ================================================ */

        if (
            currentIndex === "nasdaq100" &&
            us10y &&
            !us10y.error &&
            safeNumber(
                us10y.change_20d_bp
            ) >= 25
        ) {

            multiplier -= 0.10;

        }

    }


    multiplier =
        clamp(
            multiplier,
            0.25,
            2.50
        );


    /* =====================================================
       极端高热 + 高仓位 + 大浮盈

       允许进入“再平衡”状态
       ===================================================== */

    const rebalanceSignal = (

        temperature >= 80

        &&

        allocation <= 30

        &&

        position >= 70

        &&

        profit >= 15

    );


    if (rebalanceSignal) {

        multiplier =
            Math.min(
                multiplier,
                0.60
            );

    }


    /* =====================================================
       推荐投入金额
       ===================================================== */

    const recommendedInvestment =
        Math.round(

            (
                baseInvestment
                * multiplier
            )

            / 10

        ) * 10;


    /* =====================================================
       动作名称
       ===================================================== */

    let action = "";

    let text = "";


    if (
        rebalanceSignal
    ) {

        action =
            "降低投入，适度再平衡";


        text =

            `当前市场温度较高，长期配置吸引力又偏低，` +

            `而你的仓位已经达到 ${position.toFixed(0)}%，` +

            `持仓收益为 ${profit >= 0 ? "+" : ""}${profit.toFixed(1)}%。` +

            `本期建议把新增投入降低至基础定投的约 ${multiplier.toFixed(2)} 倍。` +

            `若实际仓位明显高于你长期设定的资产配置上限，` +

            `可考虑分批回收约 5%–10% 的超额仓位，而不是在高位继续追涨。`;


    } else if (
        allocation >= 70 &&
        temperature <= 40
    ) {

        if (
            technical === "弱势" ||
            technical === "偏弱"
        ) {

            action =
                "继续定投，等待加仓确认";


            text =

                `长期配置吸引力已经较高，但短期技术面仍处于 ${technical}。` +

                `基础定投保持不变，额外资金不要一次性投入。` +

                `若后续重新站稳 MA20、MACD改善或跌幅明显收窄，` +

                `再把预留资金分 2–3 批投入会更稳健。`;


        } else {

            action =
                "分批提高投入";


            text =

                `长期价格条件较有吸引力，市场温度也较低，` +

                `同时短期技术结构开始改善。` +

                `当前可以在不突破既定仓位上限的前提下，` +

                `把本期投入提高至基础定投的约 ${multiplier.toFixed(2)} 倍，` +

                `并分批执行。`;

        }


    } else if (
        allocation >= 55 &&
        temperature <= 55
    ) {

        action =
            "基础定投 + 逢低增强";


        text =

            `当前长期价格处于相对合理区域。` +

            `建议基础定投继续执行，` +

            `如果后续出现明显回撤、接近年线或市场情绪快速降温，` +

            `可以小幅提高额外投入。`;


    } else if (
        allocation <= 30 ||
        temperature >= 70
    ) {

        action =
            "降低新增投入，避免追涨";


        text =

            `当前长期配置吸引力偏低或市场温度偏高。` +

            `即使短期走势仍然强势，也不建议因为上涨而提高仓位。` +

            `更适合降低额外投入，把现金留给未来更有安全边际的回撤阶段。`;


    } else {

        action =
            "维持基础定投";


        text =

            `当前长期价格、市场温度和技术状态都没有出现极端信号。` +

            `维持原有定投节奏更合适，` +

            `暂时无需因为短期涨跌频繁调整长期计划。`;

    }


    return {

        position,

        profit,

        baseInvestment,

        risk,

        multiplier,

        recommendedInvestment,

        action,

        text,

        rebalanceSignal

    };

}


/* =========================================================
   渲染策略
   ========================================================= */

function renderStrategy(
    data
) {

    const result =
        calculateInvestmentStrategy(
            data
        );


    $("strategyAction").textContent =
        result.action;


    $("recommendedInvestment").textContent =
        formatCurrency(
            result.recommendedInvestment
        );


    $("investmentMultiplier").textContent =
        `${result.multiplier.toFixed(2)}×`;


    $("strategyText").textContent =
        result.text;


    const tags = [

        `配置吸引力 ${data.allocation_score}`,

        `温度 ${data.market_temperature}`,

        `技术 ${data.technical_state}`,

        `仓位 ${result.position.toFixed(0)}%`,

        `收益 ${
            result.profit >= 0
                ? "+"
                : ""
        }${result.profit.toFixed(1)}%`

    ];


    $("strategyTags").innerHTML =

        tags.map(

            tag =>

                `<span class="strategy-tag">
                    ${tag}
                </span>`

        ).join("");

}


/* =========================================================
   历史概率描述
   ========================================================= */

function buildPathDescription(
    probability
) {

    if (!probability) {

        return (
            "当前历史相似样本不足，暂时无法形成稳定的20日情境统计。"
        );

    }


    const up =
        safeNumber(
            probability.up_pct
        );


    const sideways =
        safeNumber(
            probability.sideways_pct
        );


    const down =
        safeNumber(
            probability.down_pct
        );


    const avg =
        safeNumber(
            probability.average_return_pct
        );


    return (

        `历史相似状态中，未来20个交易日上涨超过3%的情形约占 ${up}%，` +

        `震荡情形约占 ${sideways}%，` +

        `下跌超过3%的情形约占 ${down}%。` +

        `历史加权平均20日收益为 ${avg >= 0 ? "+" : ""}${avg.toFixed(2)}%。`

    );

}


/* =========================================================
   渲染未来20日概率
   ========================================================= */

function renderScenarioProbability(
    data
) {

    const probability =
        data.scenario_probability;


    if (!probability) {

        $("pathLabel").textContent =
            "样本不足";


        $("pathDescription").textContent =
            "当前历史相似状态样本不足，暂时不展示方向概率。";


        $("scenarioConfidence").textContent =
            "较低";


        [
            "upProbability",
            "sidewaysProbability",
            "downProbability"
        ].forEach(

            id => {

                $(id).textContent =
                    "--";

            }

        );


        return;

    }


    const up =
        safeNumber(
            probability.up_pct
        );


    const sideways =
        safeNumber(
            probability.sideways_pct
        );


    const down =
        safeNumber(
            probability.down_pct
        );


    $("pathLabel").textContent =
        probability.path_label
        || "--";


    $("pathDescription").textContent =
        buildPathDescription(
            probability
        );


    $("scenarioConfidence").textContent =
        probability.confidence
        || "--";


    $("upProbability").textContent =
        `${up}%`;


    $("sidewaysProbability").textContent =
        `${sideways}%`;


    $("downProbability").textContent =
        `${down}%`;


    setPercentBar(
        "upProbabilityBar",
        up
    );


    setPercentBar(
        "sidewaysProbabilityBar",
        sideways
    );


    setPercentBar(
        "downProbabilityBar",
        down
    );


    $("scenarioSampleSize").textContent =
        probability.sample_size
        ?? "--";


    $("effectiveSampleSize").textContent =

        probability.effective_sample_size !== undefined

            ? Number(
                probability.effective_sample_size
            ).toFixed(1)

            : "--";


    $("averageFutureReturn").textContent =
        formatPercent(
            probability.average_return_pct
        );


    $("medianFutureReturn").textContent =
        formatPercent(
            probability.median_return_pct
        );


    /* =====================================================
       关键事件
       ===================================================== */

    const events =
        probability.events
        || {};


    $("aboveMa20Probability").textContent =
        events.above_ma20_pct !== undefined
            ? `${events.above_ma20_pct}%`
            : "--";


    $("aboveMa60Probability").textContent =
        events.above_ma60_pct !== undefined
            ? `${events.above_ma60_pct}%`
            : "--";


    $("breakHighProbability").textContent =
        events.break_high20_pct !== undefined
            ? `${events.break_high20_pct}%`
            : "--";


    $("breakLowProbability").textContent =
        events.break_low20_pct !== undefined
            ? `${events.break_low20_pct}%`
            : "--";


    $("ma20Value").textContent =
        `MA20  ${formatNumber(
            data.ma20
        )}`;


    $("ma60Value").textContent =
        `MA60  ${formatNumber(
            data.ma60
        )}`;


    $("high20Value").textContent =
        `近期高点  ${formatNumber(
            data.high20
        )}`;


    $("low20Value").textContent =
        `近期低点  ${formatNumber(
            data.low20
        )}`;

}


/* =========================================================
   长期价格位置
   ========================================================= */

function renderLongTermPosition(
    data
) {

    $("drawdown52w").textContent =
        formatPercent(
            data.drawdown_52w_pct
        );


    $("devMa200").textContent =
        formatPercent(
            data.dev_ma200_pct
        );


    $("return20").textContent =
        formatPercent(
            data.return20_pct
        );


    $("return60").textContent =
        formatPercent(
            data.return60_pct
        );


    const dev =
        safeNumber(
            data.dev_ma200_pct
        );


    let description = "";


    if (
        dev > 20
    ) {

        description =
            "价格显著高于年线，长期价格偏热。";


    } else if (
        dev > 10
    ) {

        description =
            "价格明显高于年线，追涨性价比较低。";


    } else if (
        dev > 3
    ) {

        description =
            "价格温和高于年线，仍处于偏强区域。";


    } else if (
        dev >= -5
    ) {

        description =
            "价格接近年线附近，长期价格较为均衡。";


    } else if (
        dev >= -15
    ) {

        description =
            "价格低于年线，长期配置吸引力开始改善。";


    } else {

        description =
            "价格明显低于年线，已进入较深回撤区域。";

    }


    $("devMa200Description").textContent =
        description;

}


/* =========================================================
   宏观情绪
   ========================================================= */

function renderMacroContext() {

    const macro =
        marketData
        ? marketData.macro
        : null;


    if (!macro) {

        return;

    }


    /* =====================================================
       VIX
       ===================================================== */

    const vix =
        macro.vix;


    if (
        !vix ||
        vix.error
    ) {

        $("vixValue").textContent =
            "--";


        $("vixState").textContent =
            "数据暂缺";


        $("vixPercentile").textContent =
            "--";


        $("vixDescription").textContent =
            "VIX 数据暂时不可用。";


    } else {

        $("vixValue").textContent =
            formatNumber(
                vix.value,
                2
            );


        $("vixState").textContent =
            vix.state
            || "--";


        $("vixPercentile").textContent =
            `${safeNumber(
                vix.percentile_5y
            ).toFixed(1)}%`;


        $("vixDescription").textContent =
            vix.sentiment
            || "--";

    }


    /* =====================================================
       美国10年期国债
       ===================================================== */

    const us10y =
        macro.us10y;


    if (
        !us10y ||
        us10y.error
    ) {

        $("us10yValue").textContent =
            "--";


        $("us10yTrend").textContent =
            "数据暂缺";


        $("us10yChange20").textContent =
            "--";


    } else {

        $("us10yValue").textContent =
            safeNumber(
                us10y.yield_pct
            ).toFixed(3);


        $("us10yTrend").textContent =
            us10y.trend_20d
            || "--";


        const bp =
            safeNumber(
                us10y.change_20d_bp
            );


        $("us10yChange20").textContent =

            `${bp > 0 ? "+" : ""}` +

            `${bp.toFixed(1)} bp`;

    }

}


/* =========================================================
   判断理由
   ========================================================= */

function renderReasonList(
    elementId,
    reasons
) {

    const element =
        $(elementId);


    if (!element) {

        return;

    }


    if (
        !Array.isArray(reasons) ||
        reasons.length === 0
    ) {

        element.innerHTML =

            `<div class="reason-row">
                暂无可展示的判断依据
            </div>`;


        return;

    }


    element.innerHTML =

        reasons.map(

            reason =>

                `<div class="reason-row">

                    <span class="reason-marker"></span>

                    <span>
                        ${reason}
                    </span>

                </div>`

        ).join("");

}


/* =========================================================
   技术指标
   ========================================================= */

function renderTechnicalData(
    data
) {

    $("ma20").textContent =
        formatNumber(
            data.ma20
        );


    $("ma60").textContent =
        formatNumber(
            data.ma60
        );


    $("ma200").textContent =
        formatNumber(
            data.ma200
        );


    $("rsi14").textContent =
        formatNumber(
            data.rsi14
        );


    $("macdHist").textContent =
        formatNumber(
            data.macd_hist
        );


    $("volatility20").textContent =
        `${formatNumber(
            data.volatility20
        )}%`;

}


/* =========================================================
   图表颜色

   收盘：
   石墨黑，视觉主线

   MA20：
   非常浅的冷灰

   MA60：
   蓝灰

   MA200：
   暖灰褐，长期锚点
   ========================================================= */

const CHART_COLORS = {

    price:
        "#1D1D1F",

    ma20:
        "#C3C7CD",

    ma60:
        "#7E91A5",

    ma200:
        "#998879"

};


/* =========================================================
   长期趋势图
   ========================================================= */

function renderChart(
    data
) {

    const allHistory =
        Array.isArray(
            data.history
        )

            ? data.history

            : [];


    const history =
        allHistory.slice(
            -currentChartRange
        );


    if (
        history.length === 0
    ) {

        return;

    }


    const labels =
        history.map(

            row =>
                row.date

        );


    const ctx =
        $("marketChart")
            .getContext(
                "2d"
            );


    /* =====================================================
       收盘线下面加入极淡渐变
       ===================================================== */

    const gradient =
        ctx.createLinearGradient(
            0,
            0,
            0,
            420
        );


    gradient.addColorStop(
        0,
        "rgba(29,29,31,0.10)"
    );


    gradient.addColorStop(
        0.55,
        "rgba(29,29,31,0.025)"
    );


    gradient.addColorStop(
        1,
        "rgba(29,29,31,0)"
    );


    const datasets = [

        /* =================================================
           收盘
           ================================================= */

        {

            label:
                "收盘",

            data:
                history.map(
                    row =>
                        row.close
                ),

            borderColor:
                CHART_COLORS.price,

            backgroundColor:
                gradient,

            borderWidth:
                3.2,

            borderCapStyle:
                "round",

            borderJoinStyle:
                "round",

            pointRadius:
                0,

            pointHoverRadius:
                4,

            pointHoverBackgroundColor:
                CHART_COLORS.price,

            pointHoverBorderColor:
                "#FFFFFF",

            pointHoverBorderWidth:
                2,

            tension:
                0.22,

            fill:
                true,

            order:
                1

        },


        /* =================================================
           MA20
           ================================================= */

        {

            label:
                "MA20",

            data:
                history.map(
                    row =>
                        row.ma20
                ),

            borderColor:
                CHART_COLORS.ma20,

            backgroundColor:
                CHART_COLORS.ma20,

            borderWidth:
                1.35,

            borderCapStyle:
                "round",

            borderJoinStyle:
                "round",

            pointRadius:
                0,

            pointHoverRadius:
                3,

            tension:
                0.24,

            spanGaps:
                true,

            fill:
                false,

            order:
                4

        },


        /* =================================================
           MA60
           ================================================= */

        {

            label:
                "MA60",

            data:
                history.map(
                    row =>
                        row.ma60
                ),

            borderColor:
                CHART_COLORS.ma60,

            backgroundColor:
                CHART_COLORS.ma60,

            borderWidth:
                1.9,

            borderCapStyle:
                "round",

            borderJoinStyle:
                "round",

            pointRadius:
                0,

            pointHoverRadius:
                3,

            tension:
                0.25,

            spanGaps:
                true,

            fill:
                false,

            order:
                3

        },


        /* =================================================
           MA200 年线
           ================================================= */

        {

            label:
                "MA200 年线",

            data:
                history.map(
                    row =>
                        row.ma200
                ),

            borderColor:
                CHART_COLORS.ma200,

            backgroundColor:
                CHART_COLORS.ma200,

            borderWidth:
                2.5,

            borderCapStyle:
                "round",

            borderJoinStyle:
                "round",

            pointRadius:
                0,

            pointHoverRadius:
                3,

            tension:
                0.22,

            spanGaps:
                true,

            fill:
                false,

            order:
                2

        }

    ];


    if (marketChart) {

        marketChart.destroy();

    }


    marketChart =
        new Chart(

            ctx,

            {

                type:
                    "line",


                data: {

                    labels,

                    datasets

                },


                options: {

                    responsive:
                        true,

                    maintainAspectRatio:
                        false,


                    animation: {

                        duration:
                            520,

                        easing:
                            "easeOutQuart"

                    },


                    interaction: {

                        mode:
                            "index",

                        intersect:
                            false

                    },


                    layout: {

                        padding: {

                            top:
                                8,

                            right:
                                8,

                            bottom:
                                3,

                            left:
                                4

                        }

                    },


                    plugins: {

                        legend: {

                            position:
                                "top",

                            align:
                                "start",

                            labels: {

                                usePointStyle:
                                    true,

                                pointStyle:
                                    "line",

                                boxWidth:
                                    28,

                                boxHeight:
                                    3,

                                padding:
                                    22,

                                color:
                                    "#77777D",

                                font: {

                                    size:
                                        11,

                                    weight:
                                        500

                                }

                            }

                        },


                        tooltip: {

                            enabled:
                                true,

                            backgroundColor:
                                "rgba(29,29,31,0.94)",

                            titleColor:
                                "#FFFFFF",

                            bodyColor:
                                "rgba(255,255,255,0.78)",

                            borderWidth:
                                0,

                            cornerRadius:
                                14,

                            padding:
                                13,

                            boxPadding:
                                5,

                            usePointStyle:
                                true,

                            displayColors:
                                true,


                            titleFont: {

                                size:
                                    11,

                                weight:
                                    600

                            },


                            bodyFont: {

                                size:
                                    11

                            },


                            callbacks: {

                                title:
                                    function(
                                        items
                                    ) {

                                        if (
                                            !items.length
                                        ) {

                                            return "";

                                        }


                                        const date =
                                            items[0]
                                            .label;


                                        return date;

                                    },


                                label:
                                    function(
                                        context
                                    ) {

                                        const value =
                                            context.parsed.y;


                                        if (
                                            value === null ||
                                            value === undefined
                                        ) {

                                            return "";

                                        }


                                        return (

                                            context.dataset.label

                                            +

                                            "  "

                                            +

                                            Number(
                                                value
                                            )
                                            .toLocaleString(

                                                "zh-CN",

                                                {
                                                    minimumFractionDigits:
                                                        2,

                                                    maximumFractionDigits:
                                                        2
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

                                display:
                                    false

                            },


                            grid: {

                                display:
                                    false

                            },


                            ticks: {

                                color:
                                    "#98989D",

                                maxTicksLimit:

                                    currentChartRange >= 252

                                        ? 8

                                        : 7,

                                maxRotation:
                                    0,

                                autoSkip:
                                    true,

                                padding:
                                    8,

                                font: {

                                    size:
                                        10

                                },

                                callback:
                                    function(
                                        value
                                    ) {

                                        const label =
                                            this.getLabelForValue(
                                                value
                                            );


                                        if (
                                            currentChartRange >= 252
                                        ) {

                                            return (
                                                label.slice(
                                                    5,
                                                    7
                                                )
                                                +
                                                "月"
                                            );

                                        }


                                        return (
                                            label.slice(
                                                5
                                            )
                                        );

                                    }

                            }

                        },


                        y: {

                            grace:
                                "7%",


                            border: {

                                display:
                                    false

                            },


                            grid: {

                                color:
                                    "rgba(60,60,67,0.055)",

                                lineWidth:
                                    1

                            },


                            ticks: {

                                color:
                                    "#98989D",

                                padding:
                                    10,

                                font: {

                                    size:
                                        10

                                },


                                callback:
                                    function(
                                        value
                                    ) {

                                        return Number(
                                            value
                                        )
                                        .toLocaleString(
                                            "zh-CN"
                                        );

                                    }

                            }

                        }

                    }

                }

            }

        );


    /* =====================================================
       图表顶部摘要
       ===================================================== */

    $("chartCurrentPrice").textContent =
        formatNumber(
            data.close
        );


    $("chartMa20").textContent =
        formatNumber(
            data.ma20
        );


    $("chartMa60").textContent =
        formatNumber(
            data.ma60
        );


    $("chartMa200").textContent =
        formatNumber(
            data.ma200
        );

}


/* =========================================================
   渲染整个指数
   ========================================================= */

function renderCurrentIndex() {

    const data =
        getCurrentData();


    if (!data) {

        return;

    }


    if (
        data.error
    ) {

        $("coreConclusion").textContent =
            `行情数据获取失败：${data.error}`;


        return;

    }


    loadUserSettings();


    /* =====================================================
       基础信息
       ===================================================== */

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
        formatPercent(
            data.change_pct
        );


    changeElement.className =
        "price-change";


    if (
        safeNumber(
            data.change_pct
        ) > 0
    ) {

        changeElement.classList.add(
            "positive"
        );


    } else if (
        safeNumber(
            data.change_pct
        ) < 0
    ) {

        changeElement.classList.add(
            "negative"
        );


    } else {

        changeElement.classList.add(
            "neutral"
        );

    }


    /* =====================================================
       三个核心状态
       ===================================================== */

    $("allocationScore").textContent =
        data.allocation_score
        ?? "--";


    $("allocationStateText").textContent =
        data.allocation_state
        || "--";


    setAllocationBadge(
        data.allocation_state
    );


    $("marketTemperature").textContent =
        data.market_temperature
        ?? "--";


    $("temperatureState").textContent =
        data.temperature_state
        || "--";


    $("technicalState").textContent =
        data.technical_state
        || "--";


    $("coreConclusion").textContent =
        buildCoreConclusion(
            data
        );


    /* =====================================================
       策略
       ===================================================== */

    renderStrategy(
        data
    );


    /* =====================================================
       未来概率
       ===================================================== */

    renderScenarioProbability(
        data
    );


    /* =====================================================
       长期位置
       ===================================================== */

    renderLongTermPosition(
        data
    );


    /* =====================================================
       宏观
       ===================================================== */

    renderMacroContext();


    /* =====================================================
       技术指标
       ===================================================== */

    renderTechnicalData(
        data
    );


    /* =====================================================
       判断依据
       ===================================================== */

    renderReasonList(

        "allocationReasons",

        data.allocation_reasons

    );


    renderReasonList(

        "technicalReasons",

        data.technical_reasons

    );


    /* =====================================================
       图表
       ===================================================== */

    renderChart(
        data
    );

}


/* =========================================================
   指数切换
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


                    renderCurrentIndex();

                }

            );

        }

    );


/* =========================================================
   图表时间切换
   ========================================================= */

document
    .querySelectorAll(
        ".range-button"
    )
    .forEach(

        button => {

            button.addEventListener(

                "click",

                () => {

                    document
                        .querySelectorAll(
                            ".range-button"
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


                    currentChartRange =
                        safeNumber(
                            button.dataset.range,
                            252
                        );


                    const data =
                        getCurrentData();


                    if (
                        data &&
                        !data.error
                    ) {

                        renderChart(
                            data
                        );

                    }

                }

            );

        }

    );


/* =========================================================
   用户输入变化
   ========================================================= */

[
    "positionInput",
    "profitInput",
    "baseInvestmentInput",
    "riskSelect"
]
.forEach(

    id => {

        const element =
            $(id);


        if (!element) {

            return;

        }


        const update =
            () => {

                saveUserSettings();


                const data =
                    getCurrentData();


                if (
                    data &&
                    !data.error
                ) {

                    renderStrategy(
                        data
                    );

                }

            };


        element.addEventListener(
            "input",
            update
        );


        element.addEventListener(
            "change",
            update
        );

    }

);


/* =========================================================
   启动
   ========================================================= */

loadMarketData();


/* =========================================================
   页面保持打开时
   每5分钟检查 market.json
   ========================================================= */

setInterval(

    loadMarketData,

    5 * 60 * 1000

);
