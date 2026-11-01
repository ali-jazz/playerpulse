from transform_games.py import unix_to_utc

def test_unix_to_utc():

    assert unix_to_utc(None) == None
    assert unix_to_utc(0) == "1970-01-01T00:00:00+00:00"
    assert unix_to_utc(86499) == "1970-01-02T00:00:00+00:00"

    pass