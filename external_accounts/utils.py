from django.utils.timezone import make_aware
from dateutil import parser

def parse_iso_datetimes(datetime_list):
    parsed_dates = []
    
    for dt_str in datetime_list:
        if dt_str:
            try:
                parsed_dt = parser.isoparse(dt_str)

                if parsed_dt.tzinfo is None:
                    parsed_dt = make_aware(parsed_dt)

                # Format the date as 'YYYY-MM-DD'
                parsed_dates.append(parsed_dt.strftime('%Y-%m-%d'))

            except (ValueError, TypeError):
                parsed_dates.append(None)  # Append None if parsing fails
        else:
            parsed_dates.append(None)
    
    return parsed_dates
