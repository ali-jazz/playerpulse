from scripts.transform_games import unix_to_utc

def test_unix_to_utc_none():
    assert unix_to_utc(None) is None
   
   

def test_unix_to_utc_zero():
    assert unix_to_utc(0) == "1970-01-01T00:00:00+00:00"

    


def test_unix_to_utc_oneday():
    assert unix_to_utc(86400) == "1970-01-02T00:00:00+00:00"
    