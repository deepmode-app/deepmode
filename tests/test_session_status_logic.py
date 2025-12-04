"""
Test suite for Deepmode session status derivation logic.

This module exhaustively tests the derive_status_and_discipline function
for all planned durations: 5, 25, 50, 90 minutes, and None.

Key behaviors:
- ALL durations use ratio-based logic (no special case for 5-minute blocks):
  * ratio >= 1.0 → completed
  * 0.5 <= ratio < 1.0 → completed_early
  * 0.25 <= ratio < 0.5 → stopped_early
  * ratio < 0.25 → abandoned
- 50 and 90 are Pro-only in the UI, but backend logic is generic and tested here.
"""

import pytest

from app.routes.sessions import derive_status_and_discipline


@pytest.mark.parametrize(
    "planned, actual, expected_status, expected_disc",
    [
        # 5-minute blocks - ratio-based logic (no special case)
        (5, 0, "abandoned", 0),  # ratio = 0/5 = 0 < 0.25
        (5, 1, "abandoned", 0),  # ratio = 1/5 = 0.2 < 0.25
        (5, 1.24, "abandoned", 0),  # ratio = 1.24/5 = 0.248 < 0.25
        (5, 1.25, "stopped_early", 0),  # ratio = 1.25/5 = 0.25 >= 0.25, < 0.5
        (5, 2, "stopped_early", 0),  # ratio = 2/5 = 0.4 >= 0.25, < 0.5
        (5, 2.49, "stopped_early", 0),  # ratio = 2.49/5 = 0.498 < 0.5
        (5, 2.5, "completed_early", 1),  # ratio = 2.5/5 = 0.5 >= 0.5, < 1.0
        (5, 3, "completed_early", 1),  # ratio = 3/5 = 0.6 >= 0.5
        (5, 4, "completed_early", 1),  # ratio = 4/5 = 0.8 >= 0.5
        (5, 4.99, "completed_early", 1),  # ratio = 4.99/5 = 0.998 < 1.0
        (5, 5, "completed", 1),  # ratio = 5/5 = 1.0
        (5, 10, "completed", 1),  # ratio = 10/5 = 2.0 >= 1.0
        
        # 25-minute blocks - ratio-based logic
        # Test cases from requirements: actual in seconds converted to minutes
        # actual = 200s = 3.33 min → ratio = 3.33/25 = 0.133 < 0.25 → abandoned
        (25, 3, "abandoned", 0),  # ratio = 3/25 = 0.12 < 0.25
        # actual = 400s = 6.67 min → ratio = 6.67/25 = 0.267 >= 0.25, < 0.5 → stopped_early
        (25, 6, "stopped_early", 0),  # ratio = 6/25 = 0.24 < 0.25 (boundary)
        (25, 7, "stopped_early", 0),  # ratio = 7/25 = 0.28 >= 0.25, < 0.5
        # actual = 900s = 15 min → ratio = 15/25 = 0.6 >= 0.5, < 1.0 → completed_early
        (25, 15, "completed_early", 1),  # ratio = 15/25 = 0.6 >= 0.5
        (25, 12, "stopped_early", 0),  # ratio = 12/25 = 0.48 >= 0.25, < 0.5
        (25, 12.5, "completed_early", 1),  # ratio = 12.5/25 = 0.5 >= 0.5
        # actual = 1500s = 25 min → ratio = 25/25 = 1.0 → completed
        (25, 25, "completed", 1),  # ratio = 25/25 = 1.0
        # actual = 1800s = 30 min → ratio = 30/25 = 1.2 >= 1.0 → completed
        (25, 30, "completed", 1),  # ratio = 30/25 = 1.2 >= 1.0
        
        # 50-minute blocks - ratio-based logic
        (50, 0, "abandoned", 0),  # ratio = 0/50 = 0 < 0.25
        (50, 12, "stopped_early", 0),  # ratio = 12/50 = 0.24 < 0.25
        (50, 12.5, "stopped_early", 0),  # ratio = 12.5/50 = 0.25 >= 0.25, < 0.5
        (50, 24, "stopped_early", 0),  # ratio = 24/50 = 0.48 >= 0.25, < 0.5
        (50, 25, "completed_early", 1),  # ratio = 25/50 = 0.5 >= 0.5, < 1.0
        (50, 40, "completed_early", 1),  # ratio = 40/50 = 0.8 >= 0.5
        (50, 49, "completed_early", 1),  # ratio = 49/50 = 0.98 >= 0.5, < 1.0
        (50, 50, "completed", 1),  # ratio = 50/50 = 1.0
        (50, 70, "completed", 1),  # ratio = 70/50 = 1.4 >= 1.0
        
        # 90-minute blocks - ratio-based logic
        (90, 0, "abandoned", 0),  # ratio = 0/90 = 0 < 0.25
        (90, 22, "stopped_early", 0),  # ratio = 22/90 ≈ 0.244 < 0.25
        (90, 22.5, "stopped_early", 0),  # ratio = 22.5/90 = 0.25 >= 0.25, < 0.5
        (90, 44, "stopped_early", 0),  # ratio = 44/90 ≈ 0.489 >= 0.25, < 0.5
        (90, 45, "completed_early", 1),  # ratio = 45/90 = 0.5 >= 0.5, < 1.0
        (90, 60, "completed_early", 1),  # ratio = 60/90 ≈ 0.67 >= 0.5
        (90, 89, "completed_early", 1),  # ratio = 89/90 ≈ 0.989 >= 0.5, < 1.0
        (90, 90, "completed", 1),  # ratio = 90/90 = 1.0
        (90, 110, "completed", 1),  # ratio = 110/90 ≈ 1.22 >= 1.0
        
        # No planned duration (planned = None)
        (None, 0, "abandoned", 0),  # Theoretical
        (None, 1, "abandoned", 0),  # Too short
        (None, 4, "abandoned", 0),  # Still too short
        (None, 5, "completed", 1),  # Minimum success threshold
        (None, 30, "completed", 1),  # Any work >=5 minutes is completed
        (None, 120, "completed", 1),  # Extended work
    ],
)
def test_derive_status_and_discipline(planned, actual, expected_status, expected_disc):
    """
    Test that derive_status_and_discipline returns the correct status and discipline_score
    for all combinations of planned and actual durations.
    """
    status, disc = derive_status_and_discipline(planned, actual)
    assert status == expected_status, (
        f"Expected status '{expected_status}' for planned={planned}, actual={actual}, "
        f"but got '{status}'"
    )
    assert disc == expected_disc, (
        f"Expected discipline_score {expected_disc} for planned={planned}, actual={actual}, "
        f"but got {disc}"
    )


def test_derive_status_and_discipline_edge_cases():
    """
    Test edge cases and boundary conditions.
    """
    # Edge case: planned = 5, actual = 0 (theoretical, but should handle gracefully)
    status, disc = derive_status_and_discipline(5, 0)
    assert status == "abandoned"
    assert disc == 0
    
    # Edge case: 5-minute block at exactly 25% threshold (1.25 minutes)
    status, disc = derive_status_and_discipline(5, 1.25)
    assert status == "stopped_early"
    assert disc == 0
    
    # Edge case: 5-minute block at exactly 50% threshold (2.5 minutes)
    status, disc = derive_status_and_discipline(5, 2.5)
    assert status == "completed_early"
    assert disc == 1
    
    # Edge case: 25-minute block at exactly 25% threshold (6.25 minutes)
    # 6 minutes: ratio = 6/25 = 0.24 < 0.25 → abandoned
    status, disc = derive_status_and_discipline(25, 6)
    assert status == "abandoned"
    assert disc == 0
    
    # 6.25 minutes: ratio = 6.25/25 = 0.25 >= 0.25, < 0.5 → stopped_early
    status, disc = derive_status_and_discipline(25, 6.25)
    assert status == "stopped_early"
    assert disc == 0
    
    # 12.5 minutes: ratio = 12.5/25 = 0.5 >= 0.5, < 1.0 → completed_early
    status, disc = derive_status_and_discipline(25, 12.5)
    assert status == "completed_early"
    assert disc == 1
    
    # Edge case: 50-minute block at exactly 25% threshold (12.5 minutes)
    # 12 minutes: ratio = 12/50 = 0.24 < 0.25 → abandoned
    status, disc = derive_status_and_discipline(50, 12)
    assert status == "abandoned"
    assert disc == 0
    
    # 12.5 minutes: ratio = 12.5/50 = 0.25 >= 0.25, < 0.5 → stopped_early
    status, disc = derive_status_and_discipline(50, 12.5)
    assert status == "stopped_early"
    assert disc == 0
    
    # 25 minutes: ratio = 25/50 = 0.5 >= 0.5, < 1.0 → completed_early
    status, disc = derive_status_and_discipline(50, 25)
    assert status == "completed_early"
    assert disc == 1
    
    # Edge case: planned = None, actual = 4
    status, disc = derive_status_and_discipline(None, 4)
    assert status == "abandoned"
    assert disc == 0
    
    # Edge case: planned = None, actual = 5
    status, disc = derive_status_and_discipline(None, 5)
    assert status == "completed"
    assert disc == 1


# To run these tests:
# pytest tests/test_session_status_logic.py -q
#
# For verbose output:
# pytest tests/test_session_status_logic.py -v
#
# For coverage:
# pytest tests/test_session_status_logic.py --cov=app.routes.sessions --cov-report=term-missing

