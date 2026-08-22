/* =========================================================
   INDEX RADAR
   Frontend Strategy Engine 3.1

   核心问题：

   1. 长期配置吸引力
      → 现在值不值得增加长期资金？

   2. 价格温度
      → 当前价格相对长期锚点热不热？

   3. 市场情绪
      → 投资者现在更恐惧还是更亢奋？

   4. 短期技术
      → 现在是否适合分批动手？

   5. 历史相似情境
      → 历史上类似状态之后通常怎么走？

   重要原则：

   基础定投作为长期底仓。
   市场过热时主要减少“额外加仓”，
   而不是机械停止长期定投。

   ========================================================= */


/* =========================================================
   GLOBAL
   ========================================================= */

let marketData = null;

let currentIndex = "sse50";

let currentChartRange = 252;

let marketChart = null;

let activeHelpButton = null;


/* =========================================================
   BASIC UTILITIES
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

        "¥"

        +

        Math.round(
            number
        )
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
                    safeNumber(
                        value
                    ),
                    0,
                    100
                )}%`;

        }

    );

}


/* =========================================================
   HUMAN-FRIENDLY LABELS
   ========================================================= */


/* =========================================================
   长期配置

   尽量不用：
   高吸引力 / 中性 / 偏低

   改为：
   值得重点关注 / 适合增强 / 正常定投...
   ========================================================= */

function getAllocationActionLabel(
    data
) {

    if (
        data.allocation_action_label
    ) {

        return (
            data.allocation_action_label
        );

    }


    const score =
        safeNumber(
            data.allocation_score,
            50
        );


    if (score >= 80) {

        return "值得重点关注";

    }


    if (score >= 65) {

        return "适合适度增强";

    }


    if (score >= 45) {

        return "正常定投";

    }


    if (score >= 30) {

        return "谨慎增加";

    }


    return "暂停额外加仓";

}


/* =========================================================
   价格温度
   ========================================================= */

function getTemperatureLabel(
    score
) {

    score =
        safeNumber(
            score,
            50
        );


    if (score < 25) {

        return "价格明显偏冷";

    }


    if (score < 40) {

        return "价格偏冷";

    }


    if (score <= 60) {

        return "价格平衡";

    }


    if (score < 75) {

        return "价格偏热";

    }


    return "价格明显过热";

}


/* =========================================================
   市场情绪

   避免单纯显示：
   偏冷 / 中性 / 偏热

   改成更符合心理含义的表达。
   ========================================================= */

function getHumanSentimentLabel(
    score
) {

    score =
        safeNumber(
            score,
            50
        );


    if (score < 25) {

        return "情绪明显谨慎";

    }


    if (score < 40) {

        return "情绪偏谨慎";

    }


    if (score <= 60) {

        return "情绪平稳";

    }


    if (score < 75) {

        return "情绪偏积极";

    }


    return "情绪明显亢奋";

}


/* =========================================================
   技术状态
   ========================================================= */

function getTechnicalDisplay(
    state
) {

    switch (state) {

        case "强势":

            return "强势";


        case "偏强":

            return "偏强";


        case "中性":

            return "震荡";


        case "偏弱":

            return "偏弱";


        case "弱势":

            return "弱势";


        default:

            return state || "--";

    }

}


/* =========================================================
   LOAD JSON
   ========================================================= */

async function loadMarketData() {

    try {

        const response =
            await fetch(

                `data/market.json?t=${Date.now()}`,

                {
                    cache:
                        "no-store"
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


        updateGuideContent();

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
   CURRENT INDEX DATA
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
   LOCAL STORAGE
   ========================================================= */

function storageKey(
    field
) {

    return (

        "indexRadar_"

        +

        currentIndex

        +

        "_"

        +

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
   ALLOCATION BADGE
   ========================================================= */

function setAllocationBadge(
    label,
    score
) {

    const element =
        $("allocationState");


    if (!element) {

        return;

    }


    element.className =
        "allocation-badge";


    score =
        safeNumber(
            score,
            50
        );


    if (score >= 65) {

        element.classList.add(
            "allocation-high"
        );


    } else if (
        score >= 45
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
        label || "--";

}


/* =========================================================
   MARKET-ONLY DECISION
   首屏的“当前配置状态”

   不读取用户仓位，
   这里回答市场本身怎么样。

   个性化仓位逻辑放在“当前策略”。
   ========================================================= */

function buildMarketDecision(
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


    const sentiment =
        data.sentiment
            ? safeNumber(
                data.sentiment.score,
                50
            )
            : 50;


    const technical =
        data.technical_state
        || "中性";


    let title = "";

    let description = "";

    let signal =
        "neutral";


    /* =====================================================
       很有吸引力 + 价格冷
       ===================================================== */

    if (
        allocation >= 75
        &&
        temperature <= 35
    ) {

        signal =
            "opportunity";


        if (
            technical === "弱势" ||
            technical === "偏弱"
        ) {

            title =
                "配置机会正在改善";


            description =

                "长期价格条件已经明显改善，但短期趋势仍然偏弱。" +

                "对长期定投者而言，可以继续基础定投，并为后续企稳准备分批增强资金。";


        } else {

            title =
                "适合分批增强";


            description =

                "长期配置吸引力较高，价格温度也较低，" +

                "短期技术开始出现改善。" +

                "当前更适合分批增加长期配置，而不是一次性投入。";

        }


        return {

            title,

            description,

            signal

        };

    }


    /* =====================================================
       较高配置价值
       ===================================================== */

    if (
        allocation >= 65
        &&
        temperature <= 50
    ) {

        signal =
            "positive";


        title =
            "适合适度增强";


        description =

            "长期价格已经进入较有吸引力的区域。" +

            "基础定投可以继续，额外资金可结合市场回撤与技术确认分批投入。";


        return {

            title,

            description,

            signal

        };

    }


    /* =====================================================
       极热
       ===================================================== */

    if (
        allocation <= 30
        ||
        temperature >= 80
        ||
        (
            sentiment >= 80
            &&
            temperature >= 65
        )
    ) {

        signal =
            "caution";


        title =
            "暂停额外加仓";


        description =

            "当前价格或市场情绪已经处于较热区域。" +

            "基础定投可以保持，但暂时不建议因为上涨而额外追价，" +

            "把更多现金留给未来回撤阶段。";


        return {

            title,

            description,

            signal

        };

    }


    /* =====================================================
       略偏贵
       ===================================================== */

    if (
        allocation < 45
        ||
        temperature >= 65
    ) {

        signal =
            "watch";


        title =
            "谨慎增加";


        description =

            "当前长期配置性价比一般，或价格已经有所升温。" +

            "更适合维持基础定投，减少额外追涨，等待更好的价格位置。";


        return {

            title,

            description,

            signal

        };

    }


    /* =====================================================
       默认
       ===================================================== */

    title =
        "维持正常定投";


    description =

        "当前长期价格、市场温度和情绪均未出现明显极端状态。" +

        "现阶段更适合维持既定长期计划，而不是因短期涨跌频繁调整。";


    return {

        title,

        description,

        signal

    };

}


/* =========================================================
   HERO MARKET LABEL
   ========================================================= */

function buildHeroMarketLabel(
    data
) {

    const temperature =
        getTemperatureLabel(
            data.market_temperature
        );


    const sentiment =
        data.sentiment

            ? getHumanSentimentLabel(
                data.sentiment.score
            )

            : "情绪数据不足";


    return (

        temperature
            .replace(
                "价格",
                ""
            )

        +

        " · "

        +

        sentiment
            .replace(
                "情绪",
                ""
            )

    );

}


/* =========================================================
   CORE CONCLUSION
   ========================================================= */

function buildCoreConclusion(
    data
) {

    const decision =
        buildMarketDecision(
            data
        );


    const probability =
        data.scenario_probability;


    let probabilityText =
        "";


    if (probability) {

        probabilityText =

            ` 历史相似状态下，未来20个交易日最常见的路径为“${probability.path_label}”，` +

            `上涨 ${probability.up_pct}%、震荡 ${probability.sideways_pct}%、下跌 ${probability.down_pct}%。`;

    }


    return (

        decision.description

        +

        probabilityText

    );

}


/* =========================================================
   BASE DCA MULTIPLIER
   ========================================================= */

function getBaseEnhancedMultiplier(
    allocation
) {

    allocation =
        safeNumber(
            allocation,
            50
        );


    if (
        allocation >= 85
    ) {

        return 1.80;

    }


    if (
        allocation >= 70
    ) {

        return 1.50;

    }


    if (
        allocation >= 55
    ) {

        return 1.20;

    }


    /*
       重要：
       定投作为底仓。

       即使市场偏贵，
       默认也不因为短期指标直接把基础定投降到0。
    */

    return 1.00;

}


/* =========================================================
   RISK STYLE
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
   PERSONAL STRATEGY
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


    const sentiment =
        data.sentiment

            ? safeNumber(
                data.sentiment.score,
                50
            )

            : 50;


    const technical =
        data.technical_state
        || "中性";


    let multiplier =
        getBaseEnhancedMultiplier(
            allocation
        );


    /* =====================================================
       风格
       ===================================================== */

    multiplier +=
        getRiskAdjustment(
            risk
        );


    /* =====================================================
       价格明显偏冷

       只在配置吸引力较高时增加。
       ===================================================== */

    if (
        allocation >= 60
        &&
        temperature <= 20
    ) {

        multiplier +=
            0.25;


    } else if (
        allocation >= 60
        &&
        temperature <= 35
    ) {

        multiplier +=
            0.12;

    }


    /* =====================================================
       情绪恐慌

       恐慌本身不能作为买入理由。

       只有：
       情绪谨慎 + 长期配置吸引力较高
       才适度增加逆向配置。
       ===================================================== */

    if (
        allocation >= 60
        &&
        sentiment < 25
    ) {

        multiplier +=
            0.15;


    } else if (
        allocation >= 60
        &&
        sentiment < 40
    ) {

        multiplier +=
            0.07;

    }


    /* =====================================================
       市场过热

       不停止基础定投，
       但暂停额外增强。
       ===================================================== */

    if (
        temperature >= 75
        ||
        sentiment >= 80
        ||
        allocation <= 30
    ) {

        multiplier =
            Math.min(
                multiplier,
                1.00
            );

    }


    /* =====================================================
       高仓位

       不再增加额外资金。
       ===================================================== */

    if (
        position >= 80
    ) {

        multiplier =
            Math.min(
                multiplier,
                1.00
            );


    } else if (
        position >= 70
    ) {

        multiplier =
            Math.min(
                multiplier,
                1.15
            );

    }


    /* =====================================================
       长期值得买，但技术还没企稳

       允许：
       基础定投 + 少量增强

       不允许：
       一次性大幅增强
       ===================================================== */

    if (
        allocation >= 65
        &&
        (
            technical === "弱势"
            ||
            technical === "偏弱"
        )
    ) {

        multiplier =
            Math.min(
                multiplier,
                1.25
            );

    }


    /* =====================================================
       长期值得买 + 技术修复
       ===================================================== */

    if (
        allocation >= 65
        &&
        temperature <= 50
        &&
        (
            technical === "偏强"
            ||
            technical === "强势"
        )
    ) {

        multiplier +=
            0.10;

    }


    /* =====================================================
       大幅浮盈 + 高温

       基础定投仍然保留，
       但不增加额外投入。
       ===================================================== */

    const rebalanceSignal = (

        profit >= 15

        &&

        position >= 70

        &&

        (
            temperature >= 75
            ||
            allocation <= 30
        )

    );


    if (
        rebalanceSignal
    ) {

        multiplier =
            1.00;

    }


    /* =====================================================
       最终范围

       最低1倍：
       保留基础定投。

       最高2.2倍：
       防止模型在极端下跌时给出过激投入。
       ===================================================== */

    multiplier =
        clamp(
            multiplier,
            1.00,
            2.20
        );


    const recommendedInvestment =

        Math.round(

            (
                baseInvestment
                *
                multiplier
            )

            / 10

        ) * 10;


    let action = "";

    let text = "";


    /* =====================================================
       再平衡
       ===================================================== */

    if (
        rebalanceSignal
    ) {

        action =
            "维持定投，考虑仓位再平衡";


        text =

            `当前仓位约 ${position.toFixed(0)}%，` +

            `持仓收益 ${profit >= 0 ? "+" : ""}${profit.toFixed(1)}%，` +

            `同时市场价格已经偏热或长期配置吸引力下降。` +

            `本期维持基础定投即可，不再增加额外投入。` +

            `如果实际仓位已经明显高于你长期设定的目标范围，` +

            `可以考虑通过再平衡逐步回收部分超额仓位，而不是继续追涨。`;


    /* =====================================================
       高吸引力 + 冷
       ===================================================== */

    } else if (
        allocation >= 70
        &&
        temperature <= 40
    ) {

        if (
            technical === "弱势"
            ||
            technical === "偏弱"
        ) {

            action =
                "继续定投，预留增强资金";


            text =

                `长期配置吸引力已经达到 ${allocation}/100，` +

                `价格温度为 ${temperature}/100，长期价格条件正在改善。` +

                `但短期技术仍为“${getTechnicalDisplay(technical)}”，` +

                `因此不建议一次性投入全部额外资金。` +

                `本期可按约 ${multiplier.toFixed(2)} 倍基础定投执行，` +

                `并为重新站稳 MA20、趋势修复后的下一批加仓保留现金。`;


        } else {

            action =
                "分批增强定投";


            text =

                `长期配置吸引力较高，同时价格没有明显过热，` +

                `短期技术也开始改善。` +

                `本期可将投入提高到基础定投的约 ${multiplier.toFixed(2)} 倍，` +

                `但仍建议拆分执行，避免一次性押注短期底部。`;

        }


    /* =====================================================
       中等吸引力
       ===================================================== */

    } else if (
        allocation >= 55
        &&
        temperature <= 60
    ) {

        action =
            "基础定投 + 小幅增强";


        text =

            `当前长期价格处于相对合理区域，` +

            `适合继续基础定投。` +

            `若后续进一步回撤、价格接近MA200年线，` +

            `或市场情绪明显降温，可以逐步增加额外投入。`;


    /* =====================================================
       热
       ===================================================== */

    } else if (
        allocation <= 30
        ||
        temperature >= 75
        ||
        sentiment >= 80
    ) {

        action =
            "维持基础定投，暂停额外加仓";


        text =

            `当前市场价格或情绪已经偏热。` +

            `基础定投仍然按照长期计划执行，` +

            `但暂时不建议增加额外资金，更不建议因为短期上涨而追价。` +

            `新的现金可以留给未来回撤后长期配置吸引力重新提高的阶段。`;


    /* =====================================================
       默认
       ===================================================== */

    } else {

        action =
            "维持基础定投";


        text =

            `当前市场没有出现足够强的长期增配信号，` +

            `也没有出现需要停止长期计划的极端状态。` +

            `维持基础定投即可，等待价格、情绪或长期配置吸引力出现更明显变化。`;

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
   STRATEGY RENDER
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


    const sentimentLabel =

        data.sentiment

            ? getHumanSentimentLabel(
                data.sentiment.score
            )

            : "情绪未知";


    const tags = [

        `长期配置 ${getAllocationActionLabel(data)}`,

        getTemperatureLabel(
            data.market_temperature
        ),

        sentimentLabel,

        `技术 ${getTechnicalDisplay(
            data.technical_state
        )}`,

        `仓位 ${result.position.toFixed(0)}%`

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
   FUTURE PATH DESCRIPTION
   ========================================================= */

function buildPathDescription(
    probability
) {

    if (!probability) {

        return (
            "当前历史相似样本不足，暂时无法形成稳定的20日情境统计。"
        );

    }


    const threshold =
        safeNumber(
            probability.direction_threshold_pct,
            3
        );


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

        `历史相似市场状态中，未来20个交易日上涨超过 ${threshold}% 的情形约占 ${up}%，`

        +

        `震荡情形约占 ${sideways}%，`

        +

        `下跌超过 ${threshold}% 的情形约占 ${down}%。`

        +

        `历史加权平均20日收益为 ${avg >= 0 ? "+" : ""}${avg.toFixed(2)}%。`

    );

}


/* =========================================================
   SCENARIO PROBABILITY
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
        ]
        .forEach(

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
   LONG TERM POSITION
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


    if (dev > 20) {

        description =
            "价格显著高于年线，长期价格已经明显升温。";


    } else if (
        dev > 10
    ) {

        description =
            "价格明显高于年线，继续追价的性价比较低。";


    } else if (
        dev > 3
    ) {

        description =
            "价格温和高于年线，长期趋势仍然偏强。";


    } else if (
        dev >= -5
    ) {

        description =
            "价格位于年线附近，长期价格相对均衡。";


    } else if (
        dev >= -15
    ) {

        description =
            "价格低于年线，长期配置价格正在改善。";


    } else {

        description =
            "价格明显低于年线，已经进入较深回撤区域。";

    }


    $("devMa200Description").textContent =
        description;

}


/* =========================================================
   PER-INDEX SENTIMENT
   ========================================================= */

function renderSentiment(
    data
) {

    const sentiment =
        data.sentiment;


    if (!sentiment) {

        $("sentimentCardTitle").textContent =
            "市场情绪";


        $("sentimentScore").textContent =
            "--";


        $("sentimentState").textContent =
            "数据不足";


        $("sentimentSectionTitle").textContent =
            "市场情绪";


        $("sentimentLabel").textContent =
            "市场情绪";


        $("sentimentMainScore").textContent =
            "--";


        $("sentimentMainState").textContent =
            "--";


        $("sentimentSummary").textContent =
            "当前情绪数据暂时不可用。";


        return;

    }


    const score =
        safeNumber(
            sentiment.score,
            50
        );


    const humanState =
        getHumanSentimentLabel(
            score
        );


    /* =====================================================
       Hero
       ===================================================== */

    $("sentimentCardTitle").textContent =
        sentiment.label
        || "市场情绪";


    $("sentimentScore").textContent =
        score;


    $("sentimentState").textContent =
        humanState;


    /* =====================================================
       Section title
       ===================================================== */

    $("sentimentSectionTitle").textContent =
        sentiment.label
        || "市场情绪";


    if (
        currentIndex === "sse50"
    ) {

        $("sentimentSectionDesc").textContent =
            "使用上证50自身价格、回撤、年线与波动状态";


    } else if (
        currentIndex === "nasdaq100"
    ) {

        $("sentimentSectionDesc").textContent =
            "核心观察 VXN · Nasdaq-100 Volatility Index";


    } else {

        $("sentimentSectionDesc").textContent =
            "核心观察 VIX · S&P 500 Volatility Index";

    }


    /* =====================================================
       Main sentiment card
       ===================================================== */

    $("sentimentLabel").textContent =
        sentiment.label
        || "市场情绪";


    $("sentimentMainScore").textContent =
        score;


    $("sentimentMainState").textContent =
        humanState;


    $("sentimentSummary").textContent =
        sentiment.summary
        || "--";


    $("sentimentMethod").textContent =
        sentiment.method
        || "--";


    /* =====================================================
       Primary indicator
       ===================================================== */

    const primary =
        sentiment.primary_indicator
        || {};


    $("sentimentPrimaryName").textContent =
        primary.name
        || "--";


    if (
        primary.value === null
        ||
        primary.value === undefined
    ) {

        $("sentimentPrimaryValue").textContent =
            "--";


    } else {

        $("sentimentPrimaryValue").textContent =

            Number(
                primary.value
            )
            .toLocaleString(

                "zh-CN",

                {
                    maximumFractionDigits:
                        2
                }

            );

    }


    $("sentimentPrimaryUnit").textContent =
        primary.unit
        || "";


    $("sentimentPrimaryState").textContent =
        primary.state
        || "";


    if (
        primary.percentile_5y !== null
        &&
        primary.percentile_5y !== undefined
    ) {

        $("sentimentPrimaryPercentile").textContent =

            `5年分位 ${Number(
                primary.percentile_5y
            ).toFixed(0)}%`;


    } else {

        $("sentimentPrimaryPercentile").textContent =
            "";

    }


    /* =====================================================
       Components
       ===================================================== */

    const components =
        Array.isArray(
            sentiment.components
        )

            ? sentiment.components

            : [];


    $("sentimentComponents").innerHTML =

        components.map(

            item =>

                `<div class="sentiment-component-item">

                    <span class="sentiment-component-dot"></span>

                    <span>
                        ${item}
                    </span>

                </div>`

        ).join("");


    $("sentimentNote").textContent =
        sentiment.note
        || "";

}


/* =========================================================
   US RATE
   ========================================================= */

function renderRateEnvironment() {

    const rateSection =
        $("rateSection");


    /*
       上证50不显示美债模块
    */

    if (
        currentIndex === "sse50"
    ) {

        rateSection.style.display =
            "none";

        return;

    }


    rateSection.style.display =
        "";


    const macro =
        marketData
            ? marketData.macro
            : null;


    const us10y =
        macro
            ? macro.us10y
            : null;


    if (
        !us10y
        ||
        us10y.error
    ) {

        $("us10yValue").textContent =
            "--";


        $("us10yTrend").textContent =
            "数据暂缺";


        $("us10yChange20").textContent =
            "--";


        return;

    }


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

        `${bp > 0 ? "+" : ""}`

        +

        `${bp.toFixed(1)} bp`;

}


/* =========================================================
   LEGACY MACRO FIELDS
   兼容当前HTML隐藏节点
   ========================================================= */

function renderLegacyMacroFields() {

    if (
        !marketData ||
        !marketData.macro
    ) {

        return;

    }


    let volatilityIndex = null;


    if (
        currentIndex === "nasdaq100"
    ) {

        volatilityIndex =
            marketData.macro.vxn;


    } else if (
        currentIndex === "sp500"
    ) {

        volatilityIndex =
            marketData.macro.vix;

    }


    if (
        !volatilityIndex
        ||
        volatilityIndex.error
    ) {

        $("vixValue").textContent =
            "--";


        $("vixState").textContent =
            "--";


        $("vixPercentile").textContent =
            "--";


        $("vixDescription").textContent =
            "--";


        return;

    }


    $("vixValue").textContent =
        formatNumber(
            volatilityIndex.value
        );


    $("vixState").textContent =
        volatilityIndex.state
        || "--";


    $("vixPercentile").textContent =

        `${safeNumber(
            volatilityIndex.percentile_5y
        ).toFixed(1)}%`;


    $("vixDescription").textContent =
        volatilityIndex.name
        || "";

}


/* =========================================================
   REASON LIST
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
        !Array.isArray(
            reasons
        )
        ||
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
   TECHNICAL DATA
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
   CHART COLORS
   深海蓝 + 青绿 + 暖金
   ========================================================= */

const CHART_COLORS = {

    price:
        "#183A56",

    ma20:
        "#BBC8D3",

    ma60:
        "#507985",

    ma200:
        "#B08A54"

};


/* =========================================================
   LONG-TERM CHART
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


    const canvas =
        $("marketChart");


    if (!canvas) {

        return;

    }


    const labels =
        history.map(

            row =>
                row.date

        );


    const ctx =
        canvas.getContext(
            "2d"
        );


    const gradient =
        ctx.createLinearGradient(
            0,
            0,
            0,
            570
        );


    gradient.addColorStop(
        0,
        "rgba(24,58,86,0.16)"
    );


    gradient.addColorStop(
        0.55,
        "rgba(24,58,86,0.045)"
    );


    gradient.addColorStop(
        1,
        "rgba(24,58,86,0)"
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
                3.4,

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
                0.20,

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

            pointRadius:
                0,

            pointHoverRadius:
                3,

            borderCapStyle:
                "round",

            borderJoinStyle:
                "round",

            tension:
                0.22,

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
                2.05,

            pointRadius:
                0,

            pointHoverRadius:
                3,

            borderCapStyle:
                "round",

            borderJoinStyle:
                "round",

            tension:
                0.22,

            spanGaps:
                true,

            fill:
                false,

            order:
                3

        },


        /* =================================================
           MA200
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
                2.75,

            pointRadius:
                0,

            pointHoverRadius:
                3,

            borderCapStyle:
                "round",

            borderJoinStyle:
                "round",

            tension:
                0.20,

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
                                    30,

                                boxHeight:
                                    3,

                                padding:
                                    22,

                                color:
                                    "#68737D",

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
                                "rgba(19,39,56,0.96)",

                            titleColor:
                                "#FFFFFF",

                            bodyColor:
                                "rgba(255,255,255,0.82)",

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


                                        return (
                                            items[0].label
                                        );

                                    },


                                label:
                                    function(
                                        context
                                    ) {

                                        const value =
                                            context.parsed.y;


                                        if (
                                            value === null
                                            ||
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
                                    "#8A949D",

                                maxTicksLimit:

                                    currentChartRange >= 252

                                        ? 9

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
                                    "rgba(44,65,82,0.065)",

                                lineWidth:
                                    1

                            },


                            ticks: {

                                color:
                                    "#8A949D",

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
   HERO DECISION RENDER
   ========================================================= */

function renderDecision(
    data
) {

    const decision =
        buildMarketDecision(
            data
        );


    $("decisionTitle").textContent =
        decision.title;


    $("decisionDescription").textContent =
        decision.description;


    const signal =
        $("decisionSignal");


    signal.className =
        "decision-signal";


    signal.classList.add(

        `decision-${decision.signal}`

    );


    $("decisionAllocation").textContent =
        getAllocationActionLabel(
            data
        );


    $("decisionTemperature").textContent =
        getTemperatureLabel(
            data.market_temperature
        )
        .replace(
            "价格",
            ""
        );


    $("decisionSentiment").textContent =

        data.sentiment

            ? getHumanSentimentLabel(
                data.sentiment.score
            )
            .replace(
                "情绪",
                ""
            )

            : "--";


    $("decisionPath").textContent =

        data.scenario_probability

            ? data.scenario_probability.path_label

            : "--";

}


/* =========================================================
   FULL CURRENT INDEX
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
       BASIC INFO
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
       MARKET LABEL
       ===================================================== */

    $("heroMarketLabel").textContent =
        buildHeroMarketLabel(
            data
        );


    /* =====================================================
       ALLOCATION
       ===================================================== */

    const allocationLabel =
        getAllocationActionLabel(
            data
        );


    $("allocationScore").textContent =
        data.allocation_score
        ?? "--";


    $("allocationStateText").textContent =
        allocationLabel;


    setAllocationBadge(

        allocationLabel,

        data.allocation_score

    );


    /* =====================================================
       TEMPERATURE
       ===================================================== */

    $("marketTemperature").textContent =
        data.market_temperature
        ?? "--";


    $("temperatureState").textContent =
        getTemperatureLabel(
            data.market_temperature
        );


    /* =====================================================
       TECHNICAL
       ===================================================== */

    $("technicalState").textContent =
        getTechnicalDisplay(
            data.technical_state
        );


    /* =====================================================
       SENTIMENT
       ===================================================== */

    renderSentiment(
        data
    );


    /* =====================================================
       DECISION
       ===================================================== */

    renderDecision(
        data
    );


    /* =====================================================
       CORE CONCLUSION
       ===================================================== */

    $("coreConclusion").textContent =
        buildCoreConclusion(
            data
        );


    /* =====================================================
       PERSONAL STRATEGY
       ===================================================== */

    renderStrategy(
        data
    );


    /* =====================================================
       PROBABILITY
       ===================================================== */

    renderScenarioProbability(
        data
    );


    /* =====================================================
       LONG TERM
       ===================================================== */

    renderLongTermPosition(
        data
    );


    /* =====================================================
       RATE
       ===================================================== */

    renderRateEnvironment();


    renderLegacyMacroFields();


    /* =====================================================
       TECHNICAL DETAIL
       ===================================================== */

    renderTechnicalData(
        data
    );


    /* =====================================================
       REASONS
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
       CHART
       ===================================================== */

    renderChart(
        data
    );

}


/* =========================================================
   GUIDE
   ========================================================= */

function updateGuideContent() {

    if (
        !marketData
        ||
        !marketData.guide
    ) {

        return;

    }


    const guide =
        marketData.guide;


    if (
        guide.allocation
        &&
        $("guideAllocationText")
    ) {

        $("guideAllocationText").textContent =
            guide.allocation.meaning;

    }


    if (
        guide.price_temperature
        &&
        $("guideTemperatureText")
    ) {

        $("guideTemperatureText").textContent =
            guide.price_temperature.meaning;

    }


    if (
        guide.sentiment
        &&
        $("guideSentimentText")
    ) {

        $("guideSentimentText").textContent =
            guide.sentiment.meaning;

    }


    if (
        guide.probability
        &&
        $("guideProbabilityText")
    ) {

        $("guideProbabilityText").textContent =
            guide.probability.meaning;

    }

}


/* =========================================================
   OPEN / CLOSE GUIDE MODAL
   ========================================================= */

function openGuideModal() {

    const modal =
        $("guideModal");


    if (!modal) {

        return;

    }


    modal.classList.add(
        "open"
    );


    modal.setAttribute(
        "aria-hidden",
        "false"
    );


    document.body.classList.add(
        "modal-open"
    );

}


function closeGuideModal() {

    const modal =
        $("guideModal");


    if (!modal) {

        return;

    }


    modal.classList.remove(
        "open"
    );


    modal.setAttribute(
        "aria-hidden",
        "true"
    );


    document.body.classList.remove(
        "modal-open"
    );

}


/* =========================================================
   HELP POPOVER DATA
   ========================================================= */

function getHelpContent(
    key
) {

    const guide =
        marketData
        &&
        marketData.guide

            ? marketData.guide[
                key
            ]

            : null;


    if (guide) {

        return {

            title:
                guide.title
                || "指标说明",

            text:
                guide.meaning
                || ""

        };

    }


    const fallback = {

        allocation: {

            title:
                "长期配置吸引力",

            text:
                "回答现在是否值得增加长期资金。分数越高，代表当前长期价格条件越有吸引力。"

        },


        price_temperature: {

            title:
                "价格温度",

            text:
                "回答当前价格相对长期锚点热不热。温度低并不等于市场不好，而是代表价格机会可能正在改善。"

        },


        sentiment: {

            title:
                "市场情绪",

            text:
                "回答投资者当前更谨慎还是更亢奋。上证50、纳指100和标普500使用不同的情绪来源。"

        },


        technical: {

            title:
                "短期技术",

            text:
                "MA、RSI和MACD主要用于决定分批加减仓时点，不直接代表长期价值。"

        },


        probability: {

            title:
                "历史条件概率",

            text:
                "上涨、震荡、下跌来自历史相似状态之后20个交易日的加权统计，不是真实未来概率。"

        }

    };


    return (

        fallback[
            key
        ]

        ||

        {
            title:
                "指标说明",

            text:
                ""
        }

    );

}


/* =========================================================
   HELP POPOVER
   ========================================================= */

function openHelpPopover(
    button,
    key
) {

    const popover =
        $("helpPopover");


    if (!popover) {

        return;

    }


    activeHelpButton =
        button;


    const content =
        getHelpContent(
            key
        );


    $("helpPopoverTitle").textContent =
        content.title;


    $("helpPopoverText").textContent =
        content.text;


    popover.classList.add(
        "open"
    );


    popover.setAttribute(
        "aria-hidden",
        "false"
    );


    /*
       桌面端尽量放在按钮旁边。
       手机端CSS会让它自动居中/贴底。
    */

    const rect =
        button.getBoundingClientRect();


    const width =
        320;


    const margin =
        14;


    let left =
        rect.left
        +
        rect.width / 2
        -
        width / 2;


    left =
        clamp(

            left,

            margin,

            window.innerWidth
            -
            width
            -
            margin

        );


    let top =
        rect.bottom
        +
        10;


    if (
        top + 190
        >
        window.innerHeight
    ) {

        top =
            rect.top
            -
            190;

    }


    popover.style.left =
        `${left}px`;


    popover.style.top =
        `${Math.max(
            14,
            top
        )}px`;

}


function closeHelpPopover() {

    const popover =
        $("helpPopover");


    if (!popover) {

        return;

    }


    popover.classList.remove(
        "open"
    );


    popover.setAttribute(
        "aria-hidden",
        "true"
    );


    activeHelpButton =
        null;

}


/* =========================================================
   INDEX SWITCH
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


                    closeHelpPopover();

                    renderCurrentIndex();

                }

            );

        }

    );


/* =========================================================
   CHART RANGE
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
                        data
                        &&
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
   USER INPUT
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
                    data
                    &&
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
   GUIDE BUTTON EVENTS
   ========================================================= */

if (
    $("guideButton")
) {

    $("guideButton").addEventListener(

        "click",

        openGuideModal

    );

}


if (
    $("guideCloseButton")
) {

    $("guideCloseButton").addEventListener(

        "click",

        closeGuideModal

    );

}


const guideBackdrop =
    document.querySelector(
        ".guide-backdrop"
    );


if (
    guideBackdrop
) {

    guideBackdrop.addEventListener(

        "click",

        closeGuideModal

    );

}


/* =========================================================
   HELP BUTTON EVENTS
   ========================================================= */

document
    .querySelectorAll(
        ".help-dot"
    )
    .forEach(

        button => {

            button.addEventListener(

                "click",

                event => {

                    event.stopPropagation();


                    const key =
                        button.dataset.help;


                    if (
                        activeHelpButton === button
                        &&
                        $("helpPopover")
                        .classList
                        .contains(
                            "open"
                        )
                    ) {

                        closeHelpPopover();

                        return;

                    }


                    openHelpPopover(

                        button,

                        key

                    );

                }

            );

        }

    );


if (
    $("helpPopoverClose")
) {

    $("helpPopoverClose")
        .addEventListener(

            "click",

            closeHelpPopover

        );

}


/* =========================================================
   CLICK OUTSIDE HELP
   ========================================================= */

document.addEventListener(

    "click",

    event => {

        const popover =
            $("helpPopover");


        if (
            !popover
            ||
            !popover.classList.contains(
                "open"
            )
        ) {

            return;

        }


        if (
            popover.contains(
                event.target
            )
        ) {

            return;

        }


        if (
            event.target.closest(
                ".help-dot"
            )
        ) {

            return;

        }


        closeHelpPopover();

    }

);


/* =========================================================
   ESC
   ========================================================= */

document.addEventListener(

    "keydown",

    event => {

        if (
            event.key === "Escape"
        ) {

            closeGuideModal();

            closeHelpPopover();

        }

    }

);


/* =========================================================
   WINDOW RESIZE
   ========================================================= */

window.addEventListener(

    "resize",

    () => {

        if (
            activeHelpButton
        ) {

            closeHelpPopover();

        }

    }

);


/* =========================================================
   START
   ========================================================= */

loadMarketData();


/* =========================================================
   AUTO REFRESH
   ========================================================= */

setInterval(

    loadMarketData,

    5 * 60 * 1000

);
