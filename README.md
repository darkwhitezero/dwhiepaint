# dwhiepaint

Веб-приложение: загружаешь фото → получаешь печатную раскраску по номерам (контуры,
пронумерованные области, легенда «номер → цвет» с русскими названиями).

## Архитектура

- **frontend** — React + TypeScript + Vite
- **backend-api** — ASP.NET Core (auth, оркестрация, persistence через EF Core)
- **cv-service** — Python / FastAPI (анализ изображения, сегментация, именование цветов, экспорт)
- **postgres** — PostgreSQL 16

Всё поднимается через Docker Compose. Python-сервис не имеет доступа к БД —
только эфемерный кэш по `image_id`.

## Быстрый старт

```bash
cp .env.example .env
docker compose up --build
```

Сервисы:

| Сервис      | URL                    |
| ----------- | ---------------------- |
| frontend    | http://localhost:5173  |
| backend-api | http://localhost:5000  |
| cv-service  | внутренний, порт 8001  |
| postgres    | localhost:5432         |

Проверка здоровья:

```bash
curl http://localhost:5000/health
curl http://localhost:5000/health/db
```

## Локальная разработка (без Docker)

- `backend-api`: `dotnet run --project backend-api/DwhiePaint.Api` (нужен Postgres на 5432)
- `cv-service`: `pip install -r cv-service/requirements.txt && uvicorn app.main:app --port 8001` (из `cv-service/`)
- `frontend`: `npm install && npm run dev` (из `frontend/`)

## Статус

Реализация ведётся по фазам (см. план):

- ✅ **Phase 0 — scaffold**: скелеты сервисов, docker-compose, миграция БД.
- ✅ **Phase 1 — ядро пайплайна**: `/analyze` (авто-k), `/segment` (k-means +
  слияние регионов + контуры + нумерация), `/export` (печатный лист + легенда),
  backend-прокси, UI upload→preview→ползунок цветов→экспорт.
- ✅ **Phase 2 — аккаунты и персистентность**: JWT-авторизация, сохранение
  `images`/`paintings`/`palette_colors`, сидинг `color_dictionary` (1017 цветов),
  экраны входа/регистрации, история работ с повторным скачиванием.
- ✅ **Phase 3 — print quality**: экспорт под A4/A3 @300dpi с раскладкой,
  адаптивной к ориентации (легенда сбоку для альбомной, снизу для книжной);
  line art перерисовывается в целевом разрешении; легенда без обрезки имён.
- ⬜ **Phase 4 — polish**: шеринг/галерея, мобильная адаптация, подписанные
  URL для изображений.

### Аутентификация

Data/JSON-эндпоинты требуют JWT (`Authorization: Bearer <token>`). Байтовые
эндпоинты изображений (`/original`, `/cv-cache/…`) отдаются анонимно по
непубличному UUID, чтобы их могли грузить теги `<img>` (усилить до подписанных
URL — задача Phase 4).
