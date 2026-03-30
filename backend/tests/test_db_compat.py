from app.db_compat import adapt_legacy_args, to_legacy_query


def test_to_legacy_query_rewrites_lgd_columns_and_joins():
    query = """
        SELECT m.district_lgd::text as cdk, d.lgd_code::text as district_cdk
        FROM agri_metrics m
        JOIN districts d ON m.district_lgd = d.lgd_code
        WHERE m.district_lgd = ANY($1::int[])
    """

    legacy = to_legacy_query(query)

    assert "m.cdk as cdk" in legacy
    assert "d.cdk as district_cdk" in legacy
    assert "JOIN districts d ON m.cdk = d.cdk" in legacy
    assert "m.cdk = ANY($1::text[])" in legacy


def test_adapt_legacy_args_stringifies_numeric_cdk_sequences():
    query = "SELECT * FROM agri_metrics WHERE district_lgd = ANY($1::int[]) AND variable_name = ANY($2)"

    args = adapt_legacy_args(query, ([101, 202.0], ["wheat_yield", "rice_yield"]))

    assert args[0] == ["101", "202"]
    assert args[1] == ["wheat_yield", "rice_yield"]
