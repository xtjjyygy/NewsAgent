from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Protocol


@dataclass
class RawNewsItem:
    """原始平台条目（各平台字段可不同）。"""

    source: str
    title: str
    url: str
    heat: float
    published_at: datetime
    content: str = ""


@dataclass
class NewsItem:
    """标准化后的新闻结构。"""

    id: str
    source: str
    title: str
    url: str
    heat: float
    published_at: datetime
    content: str
    topic: str
    summary: str
    score: float


class Collector(Protocol):
    """平台采集器接口。"""

    name: str

    def fetch(self) -> Iterable[RawNewsItem]:
        ...


class MockPortalCollector:
    name = "门户"

    def fetch(self) -> Iterable[RawNewsItem]:
        now = datetime.now(timezone.utc)
        return [
            RawNewsItem(
                source=self.name,
                title="AI 芯片公司发布新一代推理加速卡",
                url="https://portal.example.com/ai-chip",
                heat=95,
                published_at=now,
                content="新品支持更高吞吐，云厂商宣布首批部署。",
            ),
            RawNewsItem(
                source=self.name,
                title="央行发布最新货币政策报告",
                url="https://portal.example.com/policy-report",
                heat=88,
                published_at=now,
                content="强调稳增长与结构性工具协同发力。",
            ),
            RawNewsItem(
                source=self.name,
                title="台风北上影响多地出行",
                url="https://portal.example.com/typhoon",
                heat=80,
                published_at=now,
                content="铁路和航班发布临时调整公告。",
            ),
        ]


class MockSocialCollector:
    name = "社交媒体"

    def fetch(self) -> Iterable[RawNewsItem]:
        now = datetime.now(timezone.utc)
        return [
            RawNewsItem(
                source=self.name,
                title="新一代AI芯片发布，云厂商已部署",
                url="https://social.example.com/post/123",
                heat=90,
                published_at=now,
                content="业内关注其功耗表现和推理成本下降。",
            ),
            RawNewsItem(
                source=self.name,
                title="某新能源车企公布季度财报超预期",
                url="https://social.example.com/post/456",
                heat=86,
                published_at=now,
                content="交付量增长带动营收与利润改善。",
            ),
            RawNewsItem(
                source=self.name,
                title="台风北上造成沿海多地交通调整",
                url="https://social.example.com/post/789",
                heat=79,
                published_at=now,
                content="公众关注停运信息与防灾提示。",
            ),
        ]


class NewsOrchestrator:
    def __init__(self, collectors: List[Collector], source_weight: Dict[str, float] | None = None) -> None:
        self.collectors = collectors
        self.source_weight = source_weight or {
            "门户": 1.0,
            "社交媒体": 0.9,
        }

    def run(self, top_n: int = 10, keywords: List[str] | None = None) -> Dict[str, object]:
        raw_items = self.collect()
        deduped = self.deduplicate(raw_items)
        enriched = [self.enrich(item) for item in deduped]
        ranked = sorted(enriched, key=lambda x: x.score, reverse=True)
        grouped = self.group_by_topic(ranked)
        tracked = self.track_keywords(ranked, keywords or [])

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "top": [self.to_jsonable(i) for i in ranked[:top_n]],
            "by_topic": {k: [self.to_jsonable(i) for i in v] for k, v in grouped.items()},
            "keyword_matches": {k: [self.to_jsonable(i) for i in v] for k, v in tracked.items()},
            "platform_top": self.platform_top(ranked, per_source=5),
        }

    def collect(self) -> List[RawNewsItem]:
        items: List[RawNewsItem] = []
        for collector in self.collectors:
            items.extend(list(collector.fetch()))
        return items

    def deduplicate(self, items: List[RawNewsItem]) -> List[RawNewsItem]:
        """
        简易去重：标题归一化后，保留热度更高的版本。
        """
        best_by_key: Dict[str, RawNewsItem] = {}
        for item in items:
            key = self.normalize_title(item.title)
            current = best_by_key.get(key)
            if current is None or item.heat > current.heat:
                best_by_key[key] = item
        return list(best_by_key.values())

    @staticmethod
    def normalize_title(title: str) -> str:
        stripped = "".join(ch.lower() for ch in title if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
        for token in ["新一代", "发布", "公布", "最新", "造成"]:
            stripped = stripped.replace(token, "")
        return stripped

    def enrich(self, item: RawNewsItem) -> NewsItem:
        topic = self.classify_topic(item)
        summary = self.summarize(item)
        score = self.score(item)
        return NewsItem(
            id=self.normalize_title(item.title),
            source=item.source,
            title=item.title,
            url=item.url,
            heat=item.heat,
            published_at=item.published_at,
            content=item.content,
            topic=topic,
            summary=summary,
            score=score,
        )

    def score(self, item: RawNewsItem) -> float:
        weight = self.source_weight.get(item.source, 1.0)
        age_hours = (datetime.now(timezone.utc) - item.published_at).total_seconds() / 3600
        freshness_bonus = max(0.0, 1.0 - age_hours / 24)
        return round(item.heat * weight * (1 + 0.1 * freshness_bonus), 2)

    @staticmethod
    def summarize(item: RawNewsItem) -> str:
        text = item.content.strip() or item.title
        if len(text) <= 36:
            return text
        return text[:36] + "…"

    @staticmethod
    def classify_topic(item: RawNewsItem) -> str:
        text = f"{item.title} {item.content}"
        mapping = {
            "科技": ["ai", "芯片", "云", "科技", "算法", "模型"],
            "财经": ["财报", "央行", "货币", "营收", "利润", "经济"],
            "社会": ["台风", "交通", "出行", "铁路", "航班"],
            "国际": ["国际", "外交", "战争", "联合国"],
        }
        lower = text.lower()
        for topic, keywords in mapping.items():
            if any(k in lower for k in keywords):
                return topic
        return "其他"

    @staticmethod
    def group_by_topic(items: List[NewsItem]) -> Dict[str, List[NewsItem]]:
        grouped: Dict[str, List[NewsItem]] = defaultdict(list)
        for item in items:
            grouped[item.topic].append(item)
        return dict(grouped)

    @staticmethod
    def track_keywords(items: List[NewsItem], keywords: List[str]) -> Dict[str, List[NewsItem]]:
        result: Dict[str, List[NewsItem]] = {}
        for kw in keywords:
            kw_lower = kw.lower()
            result[kw] = [
                item
                for item in items
                if kw_lower in item.title.lower() or kw_lower in item.content.lower()
            ]
        return result

    @staticmethod
    def to_jsonable(item: NewsItem) -> Dict[str, object]:
        data = asdict(item)
        data["published_at"] = item.published_at.isoformat()
        return data

    @staticmethod
    def platform_top(items: List[NewsItem], per_source: int = 5) -> Dict[str, List[Dict[str, object]]]:
        grouped: Dict[str, List[NewsItem]] = defaultdict(list)
        for item in items:
            grouped[item.source].append(item)

        result: Dict[str, List[Dict[str, object]]] = {}
        for source, rows in grouped.items():
            top_rows = sorted(rows, key=lambda x: x.score, reverse=True)[:per_source]
            result[source] = [NewsOrchestrator.to_jsonable(item) for item in top_rows]
        return result


def render_markdown(report: Dict[str, object]) -> str:
    lines: List[str] = ["# 今日热点简报", ""]
    lines.append(f"生成时间：{report['generated_at']}")
    lines.append("")

    lines.append("## 全网 Top 热点")
    for idx, item in enumerate(report["top"], start=1):
        lines.append(f"{idx}. **{item['title']}** ({item['source']}) - score={item['score']}")
        lines.append(f"   - 主题：{item['topic']}")
        lines.append(f"   - 摘要：{item['summary']}")
        lines.append(f"   - 链接：{item['url']}")

    lines.append("")
    lines.append("## 主题聚合")
    for topic, items in report["by_topic"].items():
        lines.append(f"### {topic}")
        for item in items:
            lines.append(f"- {item['title']} ({item['source']})")

    lines.append("")
    lines.append("## 关键词监控")
    keyword_matches: Dict[str, List[Dict[str, object]]] = report["keyword_matches"]  # type: ignore[assignment]
    if not keyword_matches:
        lines.append("- 未设置关键词")
    else:
        for kw, items in keyword_matches.items():
            lines.append(f"### {kw}")
            if not items:
                lines.append("- 无匹配")
            for item in items:
                lines.append(f"- {item['title']} ({item['source']})")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NewsAgent: 多平台热点采集与汇总")
    parser.add_argument("--top", type=int, default=10, help="输出 Top N 热点")
    parser.add_argument("--keywords", nargs="*", default=[], help="关键词监控列表")
    parser.add_argument("--json-out", type=Path, default=Path("output/report.json"), help="JSON 输出路径")
    parser.add_argument("--md-out", type=Path, default=Path("output/report.md"), help="Markdown 输出路径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    orchestrator = NewsOrchestrator(
        collectors=[
            MockPortalCollector(),
            MockSocialCollector(),
        ]
    )

    report = orchestrator.run(top_n=args.top, keywords=args.keywords)

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)

    args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.md_out.write_text(render_markdown(report), encoding="utf-8")

    print(f"生成完成: {args.json_out} / {args.md_out}")


if __name__ == "__main__":
    main()
