from collections import Counter


class StatisticsService:
    def __init__(self, repository):
        self.repository = repository

    def summary(self):
        works = self.repository.list_all()
        completed = [work for work in works if work.status == "Concluído"]
        reading = [work for work in works if work.status == "Lendo"]
        favorites = [work for work in works if work.favorite]
        pages = sum(work.progress_current for work in works if work.progress_unit == "Página")
        chapters = sum(work.progress_current for work in works if work.progress_unit == "Capítulo")
        ratings = [float(work.rating) for work in works if work.rating is not None]
        average_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0

        completed_categories = Counter(work.category for work in completed if work.category.strip())
        all_categories = Counter(work.category for work in works if work.category.strip())
        counter = completed_categories or all_categories
        top_category = counter.most_common(1)[0][0] if counter else "-"

        progress_values = []
        for work in works:
            if work.progress_total and work.progress_total > 0:
                progress_values.append(min(work.progress_current / work.progress_total, 1))
        average_progress = round((sum(progress_values) / len(progress_values)) * 100, 1) if progress_values else 0

        return {
            "total_works": len(works),
            "completed": len(completed),
            "reading": len(reading),
            "favorites": len(favorites),
            "pages_read": pages,
            "chapters_read": chapters,
            "average_rating": average_rating,
            "top_category": top_category,
            "average_progress": average_progress,
        }
