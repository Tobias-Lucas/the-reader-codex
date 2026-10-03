from collections import Counter


class StatisticsService:
    def __init__(self, repository):
        self.repository = repository

    def summary(self):
        works = self.repository.list_all()

        completed = [
            work
            for work in works
            if work.status.lower() in ("concluído", "concluido")
        ]

        pages = sum(
            work.progress_current
            for work in works
            if work.progress_unit.lower().startswith("p")
        )

        chapters = sum(
            work.progress_current
            for work in works
            if work.progress_unit.lower().startswith("c")
        )

        ratings = [
            work.rating
            for work in works
            if work.rating is not None
        ]

        average_rating = (
            round(sum(ratings) / len(ratings), 2)
            if ratings
            else 0
        )

        category_counter = Counter(
            work.category
            for work in works
        )

        top_category = (
            category_counter.most_common(1)[0][0]
            if category_counter
            else "-"
        )

        return {
            "total_works": len(works),
            "completed": len(completed),
            "pages_read": pages,
            "chapters_read": chapters,
            "average_rating": average_rating,
            "top_category": top_category,
        }
