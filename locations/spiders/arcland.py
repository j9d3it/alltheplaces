import json
from typing import Iterable

from locations.categories import Categories, Extras, apply_category, apply_yes_no
from locations.hours import DAYS, OpeningHours
from locations.items import Feature
from locations.storefinders.location_cloud import LocationCloudSpider


class ArclandSpider(LocationCloudSpider):
    name = "arcland"
    skip_auto_cc_domain = True
    api_endpoint = "https://shop.arclandservice.co.jp/ae-shop/api/proxy2/shop/list"
    website_formatter = "https://shop.arclandservice.co.jp/ae-shop/spot/detail?code={}"

    def post_process_feature(self, item: Feature, source_feature: dict, **kwargs) -> Iterable[Feature]:
        if "os" in source_feature["code"]:
            return  # skip places with fake locations

        match source_feature["categories"][0]["name"]:
            case "かつや":
                item["brand_wikidata"] = "Q2855257"
                if name := source_feature.get("name"):
                    item["branch"] = name.removeprefix("かつや ")
                if ruby := source_feature.get("ruby"):
                    item["extras"]["branch:ja-Hira"] = ruby.removeprefix("カツヤ ")
                apply_category(Categories.FAST_FOOD, item)
            case "からやま":
                item["brand_wikidata"] = "Q96145071"
                if name := source_feature.get("name"):
                    item["branch"] = name.removeprefix("からやま ")
                if ruby := source_feature.get("ruby"):
                    item["extras"]["branch:ja-Hira"] = ruby.removeprefix("カラヤマ ")
                apply_category(Categories.RESTAURANT, item)
            case _:
                item["brand"] = source_feature["categories"][0]["name"]
                item["branch"] = source_feature.get("name")
                if ruby := source_feature.get("ruby"):
                    item["extras"]["branch:ja-Hira"] = ruby
                apply_category(Categories.RESTAURANT, item)

        if phone := source_feature.get("phone"):
            item["phone"] = f"+81 {phone}"

        yield item

    def parse_detail_page(self, response, item: Feature, source_feature: dict) -> Iterable[Feature]:
        start = response.text.index("spotDetail = ") + len("spotDetail = ")
        detail = json.JSONDecoder().raw_decode(response.text, start)[0]

        hours_col = next((c for c in detail["detailColumns"] if c.get("code") == "default"), None)
        if hours_col:
            hours = {
                t["label"]: t["value"]
                for t in hours_col.get("columns", {}).get("text", [])
                if t["label"] == "営業時間"
            }
            oh = OpeningHours()
            if hours:
                hours_str = hours["営業時間"]
                # Format: "10:30～23:00(ラストオーダー22:30)"
                if "～" in hours_str:
                    times = hours_str.split("～")
                    open_time = times[0].strip()
                    close_time = times[1].split("(")[0].strip()
                    oh.add_days_range(DAYS, open_time, close_time)
            item["opening_hours"] = oh

        flags = {flag["label"]: flag["value"] == "true" for flag in detail["flags"].values()}

        apply_yes_no(Extras.PARKING, item, flags.get("駐車場あり"))
        apply_yes_no(Extras.TAKEAWAY, item, flags.get("駐車場あり"))
        apply_yes_no(Extras.DELIVERY, item, flags.get("デリバリー"))

        yield item
