# Synthetic Data Generation

## Purpose and limits

The generator creates labelled, single-currency transaction histories for local development and model evaluation. It is not representative of any real bank, population, fraud prevalence, or customer behaviour. Report metrics as synthetic-data results only.

## Reproducibility

`rtml-generate --rows N --anomaly-rate R --seed S --output PATH` uses NumPy's seeded generator and deterministic UUID4 values derived from that generator. With the same Python, NumPy, pandas, and PyArrow versions and arguments, the logical rows and parquet bytes are reproducible. `--drift` accepts `none`, `amount_inflation`, `category_mix_shift`, and `new_anomaly_pattern`; drift begins in the later portion of each customer's generated history.

## Event construction

- Each customer receives a chronological series of events. Customers are interleaved by event time in the final dataset.
- Ordinary amounts use a broad log-normal distribution; categories, payment methods, event types, ages, account tenure, locations, and devices have overlapping distributions.
- The default intended anomaly archetypes are amount spikes, rapid transaction bursts, new context, repeated prior failures, small card-testing amounts, and odd-hour transactions. Archetypes overlap normal values; labels receive 1.5% independent flip noise.
- Missing values are injected for customer age, location, and device type. The online event schema still requires the contract's mandatory fields.
- `amount_inflation` raises later amounts; `category_mix_shift` changes the later merchant mix; `new_anomaly_pattern` introduces a later category/amount combination into the labels.

The requested anomaly rate is the intended rate before constraints and label noise. For example, a repeated-failure archetype is only labelled as such when at least two failures are present in the customer's prior 24-hour window. Small datasets can deviate materially due to sampling; use larger datasets for rate estimates.

## Point-in-time aggregates

For each customer, events are processed in ascending timestamp order. The current event's `transaction_count_24h`, `previous_failed_transactions`, and `average_transaction_amount` are calculated from prior events only. The 24-hour window excludes events older than `timestamp - 24 hours`; the average uses all prior transactions and is null for the first transaction. The current event is added to history only after its row is assembled. No label participates in any aggregate or feature input.

## Data contract and label boundary

`rtml.data.schemas.TransactionEvent` validates online JSON events and forbids extra fields, including `is_anomaly`. `TrainingRecord` adds the offline label for generated parquet. The producer must serialize only `TransactionEvent` fields. Any delayed ground-truth stream is a separate future-phase contract.

## Validation

Unit tests cover seeded equality, event-schema acceptance, label exclusion, observed anomaly-rate tolerance, drift scenario generation, and aggregates against a prior-only reference replay. The checked-in CSV is a compact schema/example fixture, not a substitute for generator output or a statistically useful training set.