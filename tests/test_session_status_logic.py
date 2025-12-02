"""
Test suite for Deepmode session status derivation logic.

This module exhaustively tests the derive_status_and_discipline function
for all planned durations: 5, 25, 50, 90 minutes, and None.

Key behaviors:
- 5-minute planned sessions are "micro successes": any real work >=1 minute is rewarded.
- 25 / 50 / 90 follow the strict >=5 rule for success.
- 50 and 90 are Pro-only in the UI, but backend logic is generic and tested here.
"""

import pytest

from app.routes.sessions import derive_status_and_discipline


@pytest.mark.parametrize(
    "planned, actual, expected_status, expected_disc",
    [
        # 5-minute "inertia" blocks - special handling: >=1 minute is rewarded
        (5, 0, "abandoned", 0),  # Theoretical (max(1, ...) prevents this in practice)
        (5, 1, "completed_early", 1),  # Any real work is rewarded
        (5, 3, "completed_early", 1),  # Still early but counts as success
        (5, 4, "completed_early", 1),  # Just under planned
        (5, 5, "completed", 1),  # Exactly planned
        (5, 10, "completed", 1),  # Overtime
        
        # 25-minute blocks - strict >=5 rule
        (25, 0, "abandoned", 0),  # Theoretical
        (25, 1, "abandoned", 0),  # Too short
        (25, 4, "abandoned", 0),  # Still too short
        (25, 5, "completed_early", 1),  # Minimum success threshold
        (25, 10, "completed_early", 1),  # Early but successful
        (25, 24, "completed_early", 1),  # Just under planned
        (25, 25, "completed", 1),  # Exactly planned
        (25, 30, "completed", 1),  # Overtime
        (25, 70, "completed", 1),  # Significant overtime
        
        # 50-minute blocks - strict >=5 rule
        (50, 0, "abandoned", 0),  # Theoretical
        (50, 1, "abandoned", 0),  # Too short
        (50, 4, "abandoned", 0),  # Still too short
        (50, 5, "completed_early", 1),  # Minimum success threshold
        (50, 40, "completed_early", 1),  # Early but successful
        (50, 49, "completed_early", 1),  # Just under planned
        (50, 50, "completed", 1),  # Exactly planned
        (50, 70, "completed", 1),  # Overtime
        (50, 120, "completed", 1),  # Significant overtime
        
        # 90-minute blocks - strict >=5 rule
        (90, 0, "abandoned", 0),  # Theoretical
        (90, 1, "abandoned", 0),  # Too short
        (90, 4, "abandoned", 0),  # Still too short
        (90, 5, "completed_early", 1),  # Minimum success threshold
        (90, 60, "completed_early", 1),  # Early but successful
        (90, 89, "completed_early", 1),  # Just under planned
        (90, 90, "completed", 1),  # Exactly planned
        (90, 110, "completed", 1),  # Overtime
        (90, 150, "completed", 1),  # Significant overtime
        
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
    
    # Edge case: planned = 5, actual = 1 (minimum success for micro block)
    status, disc = derive_status_and_discipline(5, 1)
    assert status == "completed_early"
    assert disc == 1
    
    # Edge case: planned = 6 (just above micro block threshold)
    status, disc = derive_status_and_discipline(6, 4)
    assert status == "abandoned"  # Should use general rule, not micro block rule
    assert disc == 0
    
    status, disc = derive_status_and_discipline(6, 5)
    assert status == "completed_early"  # >= 5 but < planned
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

