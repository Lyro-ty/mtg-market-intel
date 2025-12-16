"""
Time-series interpolation utilities for API routes.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List

import structlog

logger = structlog.get_logger()


def interpolate_missing_points(
    points: List[Dict[str, Any]],
    start_date: datetime,
    end_date: datetime,
    bucket_minutes: int
) -> List[Dict[str, Any]]:
    """
    Fill gaps in time-series data using forward-fill and linear interpolation.

    Improved with:
    - Minimum data point requirements
    - Validation of interpolated values
    - Better handling of sparse data
    - Maximum gap limits to prevent excessive interpolation

    Args:
        points: List of points with 'timestamp' and 'indexValue' keys
        start_date: Start of the time range
        end_date: End of the time range
        bucket_minutes: Size of each bucket in minutes

    Returns:
        List of points with gaps filled
    """
    if not points:
        return []

    # MINIMUM DATA REQUIREMENT: Need at least 2 points for meaningful interpolation
    if len(points) < 2:
        logger.warning(
            "Insufficient data points for interpolation",
            point_count=len(points),
            bucket_minutes=bucket_minutes
        )
        # Return original points if we have at least one, otherwise empty
        return points if points else []

    # Convert timestamps to datetime objects for easier manipulation
    point_dict = {}
    skipped_count = 0
    for point in points:
        try:
            if isinstance(point['timestamp'], str):
                ts = datetime.fromisoformat(point['timestamp'].replace('Z', '+00:00'))
            else:
                ts = point['timestamp']
            # Validate indexValue is a number
            index_val = float(point['indexValue'])
            # Relaxed bounds: index values can be 0-10000 (normalized to base 100, so typically 50-200)
            # But allow wider range to handle edge cases
            if index_val < -1000 or index_val > 100000:  # Very wide bounds to catch only extreme outliers
                logger.warning(
                    "Extreme index value detected, skipping",
                    value=index_val,
                    timestamp=ts.isoformat() if isinstance(ts, datetime) else str(ts)
                )
                skipped_count += 1
                continue
            point_dict[ts] = index_val
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(
                "Invalid point data in interpolation",
                error=str(e),
                point=point
            )
            skipped_count += 1
            continue

    if skipped_count > 0:
        logger.warning(
            "Skipped points during interpolation validation",
            skipped=skipped_count,
            total=len(points),
            remaining=len(point_dict)
        )

    if not point_dict:
        logger.warning("No valid points after validation")
        return []

    # Generate all expected bucket timestamps
    bucket_timedelta = timedelta(minutes=bucket_minutes)
    expected_times = []
    current = start_date
    while current <= end_date:
        expected_times.append(current)
        current += bucket_timedelta

    # Calculate maximum gap size - be very lenient for sparse data
    # If we have data points, allow large gaps to ensure we return something
    # Only skip if gap is larger than 90% of the range
    max_gap_buckets = max(100, int(len(expected_times) * 0.9))  # Allow gaps up to 90% of range

    # Fill missing points using forward-fill, then linear interpolation
    filled_points = []
    last_value = None
    last_time = None
    gap_size = 0

    # Helper to find closest matching timestamp (handles timezone/precision differences)
    def find_closest_timestamp(target_time, point_dict, tolerance_seconds=60):
        """Find closest timestamp in point_dict within tolerance."""
        # First try exact match
        if target_time in point_dict:
            return target_time, point_dict[target_time]

        # Try to find within tolerance (1 minute)
        for ts, value in point_dict.items():
            time_diff = abs((target_time - ts).total_seconds())
            if time_diff <= tolerance_seconds:
                return ts, value
        return None, None

    for i, expected_time in enumerate(expected_times):
        # Try exact match first, then closest match
        matched_ts, matched_value = find_closest_timestamp(expected_time, point_dict)

        if matched_ts is not None:
            # We have actual data for this bucket (exact or close match)
            last_value = matched_value
            last_time = expected_time
            gap_size = 0
            filled_points.append({
                'timestamp': expected_time.isoformat(),
                'indexValue': matched_value
            })
            # Remove from point_dict to avoid reusing
            if matched_ts in point_dict:
                del point_dict[matched_ts]
        elif last_value is not None:
            gap_size += 1

            # Forward-fill: use last known value for small gaps (up to 3 buckets)
            if gap_size <= 3:
                filled_points.append({
                    'timestamp': expected_time.isoformat(),
                    'indexValue': last_value
                })
            elif gap_size <= max_gap_buckets:
                # For larger gaps, try linear interpolation
                # Find next known value for interpolation
                next_value = None
                next_time = None
                for future_time in expected_times[i+1:]:
                    matched_ts, matched_val = find_closest_timestamp(future_time, point_dict)
                    if matched_ts is not None:
                        next_value = matched_val
                        next_time = future_time
                        break

                if next_value is not None and last_time is not None:
                    # Linear interpolation between last and next
                    time_diff = (next_time - last_time).total_seconds()
                    if time_diff > 0:
                        interp_factor = (expected_time - last_time).total_seconds() / time_diff
                        interp_value = last_value + (next_value - last_value) * interp_factor

                        # Validate interpolated value is reasonable
                        if -1000 <= interp_value <= 100000:
                            filled_points.append({
                                'timestamp': expected_time.isoformat(),
                                'indexValue': round(interp_value, 2)
                            })
                        else:
                            # Use last value if interpolation produces unreasonable value
                            filled_points.append({
                                'timestamp': expected_time.isoformat(),
                                'indexValue': last_value
                            })
                else:
                    # No next value found, use last value (forward-fill)
                    filled_points.append({
                        'timestamp': expected_time.isoformat(),
                        'indexValue': last_value
                    })
            # If gap is too large (> max_gap_buckets), skip this bucket
            # But we'll still return actual data points when we find them
        else:
            # No data yet, find next known value
            next_value = None
            next_time = None
            for future_time in expected_times[i+1:]:
                matched_ts, matched_val = find_closest_timestamp(future_time, point_dict)
                if matched_ts is not None:
                    next_value = matched_val
                    next_time = future_time
                    break

            if next_value is not None:
                # Use next value if no previous value
                filled_points.append({
                    'timestamp': expected_time.isoformat(),
                    'indexValue': next_value
                })
                last_value = next_value
                last_time = next_time
                gap_size = 0
            else:
                # No data available, skip this bucket
                continue

    # Log if we had to interpolate a lot
    if len(filled_points) > len(point_dict) * 2:
        logger.info(
            "Extensive interpolation performed",
            original_points=len(point_dict),
            filled_points=len(filled_points),
            bucket_minutes=bucket_minutes
        )

    # CRITICAL FIX: If interpolation returned fewer points than original, something went wrong
    # Return original points to ensure we don't lose data
    if len(filled_points) < len(point_dict) and len(point_dict) > 0:
        logger.warning(
            "Interpolation returned fewer points than original data",
            original_count=len(point_dict),
            interpolated_count=len(filled_points),
            bucket_minutes=bucket_minutes
        )
        # Return original points converted to the expected format
        original_points_list = []
        for ts, value in point_dict.items():
            original_points_list.append({
                'timestamp': ts.isoformat() if isinstance(ts, datetime) else str(ts),
                'indexValue': value
            })
        # Sort by timestamp
        original_points_list.sort(key=lambda x: x['timestamp'])
        return original_points_list

    return filled_points
