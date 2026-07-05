# dwhiepaint — frontend

React 19 + TypeScript + Vite. Интерфейс раскраски по номерам: загрузка,
редактор с зумом/слоями/подсветкой палитры, история и кабинет. Общий обзор
проекта — в [корневом README](../README.md).

## Команды

```bash
npm install
npm run dev      # дев-сервер на http://localhost:5173
npm run build    # проверка типов (tsc) + production-сборка
npm run test     # модульные тесты (Vitest)
npm run lint     # Oxlint
```

Адрес backend берётся из `VITE_API_BASE_URL` (по умолчанию
`http://localhost:5000`).

## Ориентиры в коде

- `src/api.ts` — весь HTTP-слой и типы.
- `src/Editor.tsx` — загрузка → постановка задачи → опрос прогресса → результат.
- `src/ResultViewer.tsx` — зум/пан, переключение слоёв, инлайн-SVG с подсветкой.
- `src/PalettePanel.tsx` — палитра и подсветка областей выбранного цвета.
- `src/index.css` — токены темы, стекло и aurora-подложка; `src/App.css` — вёрстка
  и «REDESIGN» блок стеклянных стилей.
