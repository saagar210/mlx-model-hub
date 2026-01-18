# FSRS: Free Spaced Repetition Scheduler Algorithm

FSRS (Free Spaced Repetition Scheduler) is a modern spaced repetition algorithm that outperforms SM-2 (used by Anki) through machine learning optimization and a more accurate memory model.

## What is Spaced Repetition?

Spaced repetition optimizes learning by scheduling reviews at increasing intervals. Items you know well are reviewed less frequently; items you struggle with are reviewed more often.

## FSRS vs SM-2 (Anki's Algorithm)

| Aspect | SM-2 | FSRS |
|--------|------|------|
| Memory Model | Simple exponential | DSR (Difficulty, Stability, Retrievability) |
| Parameters | Fixed 5 parameters | 17 optimizable parameters |
| Personalization | Limited | Learns from your history |
| Accuracy | ~70% | ~85% prediction accuracy |
| Interval Calculation | Ease factor based | Stability-based with forgetting curve |

## Core Concepts

### The Three Variables

1. **Difficulty (D)**: How hard the card is (1-10 scale)
2. **Stability (S)**: Days until retention drops to 90%
3. **Retrievability (R)**: Current probability of recall (0-1)

### The Forgetting Curve

FSRS models memory decay using:

```
R(t) = (1 + t / (9 * S))^(-1)
```

Where:
- `R(t)` = retrievability at time t
- `S` = stability (days)
- `t` = days since last review

## FSRS Parameters

The 17 FSRS parameters control:

```python
FSRS_PARAMETERS = {
    "w": [
        0.4,    # w0: Initial stability for Again
        0.6,    # w1: Initial stability for Hard
        2.4,    # w2: Initial stability for Good
        5.8,    # w3: Initial stability for Easy
        4.93,   # w4: Difficulty weight
        0.94,   # w5: Stability decay
        0.86,   # w6: Stability growth
        0.01,   # w7: Retrievability weight
        1.49,   # w8: Stability after forgetting
        0.14,   # w9: Difficulty after forgetting
        0.94,   # w10: Hard penalty
        2.18,   # w11: Easy bonus
        0.05,   # w12: Short-term stability
        0.34,   # w13: Stability ceiling
        1.26,   # w14: Difficulty floor
        0.29,   # w15: Difficulty ceiling
        2.61    # w16: Fuzz factor
    ]
}
```

## Using py-fsrs

### Installation

```bash
pip install fsrs
```

### Basic Usage

```python
from fsrs import FSRS, Card, Rating
from datetime import datetime

# Initialize scheduler
f = FSRS()

# Create a new card
card = Card()

# Review with rating (Again=1, Hard=2, Good=3, Easy=4)
now = datetime.now()
scheduling_cards = f.repeat(card, now)

# Get next review based on rating
card_after_good = scheduling_cards[Rating.Good].card
print(f"Next review in: {card_after_good.due - now}")
```

### Rating Scale

```python
from fsrs import Rating

Rating.Again  # 1 - Complete failure, reset
Rating.Hard   # 2 - Recalled with difficulty
Rating.Good   # 3 - Recalled with some effort
Rating.Easy   # 4 - Instant recall
```

### Full Review Flow

```python
from fsrs import FSRS, Card, Rating
from datetime import datetime, timezone

def review_card(card: Card, rating: int) -> Card:
    """Process a card review and return updated card."""
    f = FSRS()
    now = datetime.now(timezone.utc)

    # Get scheduling options for all ratings
    scheduling = f.repeat(card, now)

    # Apply the chosen rating
    rating_enum = Rating(rating)
    result = scheduling[rating_enum]

    print(f"Difficulty: {result.card.difficulty:.2f}")
    print(f"Stability: {result.card.stability:.2f} days")
    print(f"Next due: {result.card.due}")

    return result.card

# Example usage
card = Card()
card = review_card(card, 3)  # Good
card = review_card(card, 3)  # Good again
card = review_card(card, 2)  # Hard
```

### Custom Parameters

```python
from fsrs import FSRS, Parameters

# Optimize parameters from review history
custom_params = Parameters(
    w=[0.4, 0.6, 2.4, 5.8, 4.93, 0.94, 0.86, 0.01,
       1.49, 0.14, 0.94, 2.18, 0.05, 0.34, 1.26, 0.29, 2.61],
    request_retention=0.9,  # Target 90% recall
    maximum_interval=365,    # Max 1 year between reviews
)

f = FSRS(custom_params)
```

## Integration with Databases

```python
from dataclasses import asdict
from fsrs import Card, FSRS, Rating
import json

def card_to_dict(card: Card) -> dict:
    """Serialize card for database storage."""
    return {
        "due": card.due.isoformat(),
        "stability": card.stability,
        "difficulty": card.difficulty,
        "elapsed_days": card.elapsed_days,
        "scheduled_days": card.scheduled_days,
        "reps": card.reps,
        "lapses": card.lapses,
        "state": card.state.value,
        "last_review": card.last_review.isoformat() if card.last_review else None,
    }

def dict_to_card(data: dict) -> Card:
    """Deserialize card from database."""
    from fsrs import State
    from datetime import datetime

    card = Card()
    card.due = datetime.fromisoformat(data["due"])
    card.stability = data["stability"]
    card.difficulty = data["difficulty"]
    card.elapsed_days = data["elapsed_days"]
    card.scheduled_days = data["scheduled_days"]
    card.reps = data["reps"]
    card.lapses = data["lapses"]
    card.state = State(data["state"])
    if data["last_review"]:
        card.last_review = datetime.fromisoformat(data["last_review"])
    return card
```

## FSRS States

Cards progress through states:

```python
from fsrs import State

State.New       # 0 - Never reviewed
State.Learning  # 1 - Initial learning phase
State.Review    # 2 - Normal review cycle
State.Relearning # 3 - Relearning after lapse
```

## Optimization

FSRS can optimize parameters from your review history:

```python
from fsrs import FSRS
from fsrs.optimizer import Optimizer

# Collect review logs: (card_id, rating, review_time, scheduled_days)
review_logs = [...]

# Optimize parameters
optimizer = Optimizer()
optimized_params = optimizer.fit(review_logs)

# Use optimized scheduler
f = FSRS(optimized_params)
```

## Best Practices

1. **Consistent ratings**: Rate honestly for better optimization
2. **Daily reviews**: Review due cards daily for best results
3. **Target retention**: 90% is recommended (85-95% range)
4. **Maximum interval**: 180-365 days prevents over-spacing
5. **Optimize periodically**: Re-optimize after 1000+ reviews

## References

- FSRS GitHub: https://github.com/open-spaced-repetition/py-fsrs
- FSRS Algorithm Paper: "A Stochastic Shortest Path Algorithm for Optimizing Spaced Repetition Scheduling"
- Anki FSRS Integration: Available in Anki 23.10+
