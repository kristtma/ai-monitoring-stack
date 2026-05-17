# DevOps Monitoring Stack with AI Alerting

[![Docker](https://img.shields.io/badge/Docker-Compose-blue)](https://docs.docker.com/compose/)
[![Prometheus](https://img.shields.io/badge/Prometheus-2.x-orange)](https://prometheus.io/)
[![Grafana](https://img.shields.io/badge/Grafana-latest-yellow)](https://grafana.com/)
[![Python](https://img.shields.io/badge/Python-3.13-green)](https://python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-lightgrey)](LICENSE)

Полноценный стек мониторинга микросервисной архитектуры с **AI-аналитикой аномалий**. Docker-контейнеры имитируют реальные серверы, Prometheus + Grafana собирают метрики, ML-сервис предсказывает сбои до их возникновения.

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                        ХОСТ                                  │
└──────────────────────────┬──────────────────────────────────┘
                           │ Docker Compose
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  #1 Backend  │   │  #2 Database │   │  #3 Frontend │
│  FastAPI     │   │  PostgreSQL  │   │  nginx       │
│  :8002       │   │  :5432       │   │  :80         │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          ▼
        ┌─────────────────────────────────────┐
        │           МОНИТОРИНГ СТЕК           │
        ├─────────────────────────────────────┤
        │  Prometheus      :9090              │
        │  Grafana         :3000              │
        │  cAdvisor        :8080              │
        │  Node Exporter   :9100              │
        │  Alertmanager    :9093              │
        │  postgres_exporter :9187            │
        │  nginx_exporter  :9113              │
        │  Incident Dashboard :8001           │
        ├─────────────────────────────────────┤
        │  ML-SERVICE   :8500              │
        │  IsolationForest + LinearRegression │
        │  Аномалии и прогноз диска           │
        └─────────────────────────────────────┘
```

---

## Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone https://github.com/<your-username>/ai-monitoring-stack.git
cd ai-monitoring-stack
```

### 2. Настроить переменные окружения

```bash
cp .env.example .env
# Отредактировать .env при необходимости
```

### 3. Запустить весь стек одной командой

```bash
docker-compose up -d
```

### 4. Проверить, что всё запущено

```bash
docker-compose ps
```

---

## Доступные сервисы

| Сервис | URL | Описание |
|--------|-----|----------|
| Frontend | http://localhost | Лендинг с навигацией|
| Backend API | http://localhost:8002 | Генератор нагрузок |
| Grafana | http://localhost:3000 | Дашборды (admin / admin123) |
| Prometheus | http://localhost:9090 | Хранилище метрик |
| Alertmanager | http://localhost:9093 | Управление алертами |
| Incident Dashboard | http://localhost:8001 | История инцидентов |
| ML-сервис | http://localhost:8500 | AI-аналитика аномалий |
| cAdvisor | http://localhost:8080 | Метрики контейнеров |

---

## ML-сервис (AI Alerting)

ML-сервис анализирует метрики каждые 60 секунд:

**Алгоритмы:**
- **IsolationForest** (scikit-learn) — обнаружение аномалий в CPU, RAM, RPS, latency
- **LinearRegression** (numpy) — прогноз времени до заполнения диска

**Метрики, публикуемые в Prometheus:**
```
ml_anomaly_score{metric_name}        # Оценка аномальности (выше = хуже)
ml_anomaly_detected{metric_name}     # 1 = аномалия обнаружена
ml_disk_hours_remaining              # Часов до заполнения диска
ml_predicted_value{metric_name}      # Прогноз на 5 минут вперёд
ml_training_samples{metric_name}     # Размер обучающей выборки
ml_last_analysis_timestamp           # Время последнего запуска
```

**API предсказаний:**
```bash
curl http://localhost:8500/predictions
```

Пример ответа:
```json
{
  "status": "ok",
  "data": {
    "cpu_usage":     {"current": 12.4, "predicted_5min": 15.1, "anomaly_score": 0.05, "is_anomaly": false},
    "memory_usage":  {"current": 45.2, "predicted_5min": 46.0, "anomaly_score": 0.08, "is_anomaly": false},
    "disk_forecast": {"free_percent_now": 68.3, "hours_until_full": null, "trend": "stable"},
    "last_updated":  "2026-05-17T14:30:00"
  }
}
```

---

## Сценарии демонстрации

### Сценарий 1 — Нагрузочное тестирование

```bash
# Простой скрипт
python load_test.py --threads 50

```

**Результат:** Grafana покажет рост CPU/RAM и RPS; ML-сервис может зафиксировать аномалию.

### Сценарий 2 — Сбой контейнера

```bash
docker-compose stop web
```

**Результат:** Через 30 сек Prometheus фиксирует потерю метрик - Alertmanager - Incident Dashboard.

```bash
docker-compose start web
```

### Сценарий 3 — Утечка памяти

```bash
python load_test.py --leak --leak-chunks 10

curl -X POST "http://localhost:8002/test/memory_leak?chunks=50"

# Очистить
curl -X DELETE http://localhost:8002/test/memory_leak
```

**Результат:** График памяти растёт - ML-сервис обнаруживает аномалию - алерт `MLAnomalyMemory`.

---

## Структура проекта

```
ai-monitoring-stack/
├── docker-compose.yml          # Весь стек одной командой
├── .env               # Переменные окружения
├── Dockerfile                  # Backend + alert-dashboard
├── main.py                     # FastAPI backend (Контейнер #1)
├── alert_dashboard.py          # Дашборд инцидентов
├── load_test.py                # Простой нагрузочный тест (threading)
├── locustfile.py               # Locust-сценарии нагрузки
├── requirements.txt            # Зависимости backend
│
├── ml_service/                 # ML-сервис аномальной аналитики
│   ├── Dockerfile
│   ├── ml_service.py           # IsolationForest + LinearRegression
│   └── requirements.txt
│
├── frontend/                   # Контейнер #3: nginx
│   ├── nginx.conf
│   └── html/index.html
│
├── prometheus_data/            # Конфиги мониторинга
│   ├── prometheus.yml
│   ├── alert_rules.yml         # Алерты 
│   └── alertmanager.yml
│
├── grafana_data/
│   └── provisioning/           # Автонастройка Grafana
│       ├── datasources/
│       └── dashboards/
│
├── templates/
│   └── index.html              # UI генератора нагрузок
│
└── screenshots/                # Скриншоты работающей системы
```

---

## Мониторинг: что собирается

| Источник | Метрики |
|----------|---------|
| cAdvisor | CPU %, Memory MB, Network I/O, Disk I/O каждого контейнера |
| Node Exporter | CPU/RAM хоста, место на диске, сетевые соединения |
| FastAPI (backend) | RPS, latency p50/p95/p99, ошибки 4xx/5xx |
| postgres_exporter | Подключения к БД, размер базы, медленные запросы |
| nginx_exporter | Активные соединения, запросы, статус |
| ML-сервис | Anomaly score, бинарный флаг аномалии, прогноз диска |

---

## Остановка стека

```bash
docker-compose down          
docker-compose down -v     
```

---

## Технологический стек

| Категория | Технологии |
|-----------|-----------|
| Backend | Python 3.13, FastAPI, Uvicorn |
| Database | PostgreSQL 16 |
| Frontend | nginx Alpine |
| Monitoring | Prometheus, Grafana, cAdvisor, Node Exporter, Alertmanager |
| Exporters | postgres_exporter, nginx-prometheus-exporter |
| AI/ML | scikit-learn (IsolationForest), numpy (LinearRegression) |
| Load Testing | Locust, Python threading |
| Orchestration | Docker, Docker Compose |
