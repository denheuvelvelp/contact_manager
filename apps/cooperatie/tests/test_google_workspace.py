from shared.google_workspace import GoogleWorkspaceManager


def test_google_workspace_unconfigured_simulation():
    mgr = GoogleWorkspaceManager()
    # Zonder credentials moet is_configured False zijn
    assert not mgr.is_configured()

    res = mgr.sync_mailinglijst(
        group_email="garages",
        group_name="Garages",
        description="Mailinglijst voor garages",
        member_emails=["lid1@example.com", "lid2@example.com", "invalid-email", ""]
    )
    assert res["success"] is True
    assert res["mode"] == "simulatie"
    assert res["group_email"] == "garages@denheuvelvelp.nl"
    assert res["member_count"] == 2
    assert "lid1@example.com" in res["members"]
    assert "lid2@example.com" in res["members"]
    assert "invalid-email" not in res["members"]


def test_google_workspace_email_normalization():
    mgr = GoogleWorkspaceManager()
    res = mgr.sync_mailinglijst(
        group_email="BEWONERS@DENHEUVELVELP.NL",
        group_name="Bewoners",
        description="",
        member_emails=["jan@example.com", "JAN@EXAMPLE.COM"]
    )
    assert res["group_email"] == "bewoners@denheuvelvelp.nl"
    # Deduplicatie van hoofd/kleine letters
    assert res["member_count"] == 1
    assert res["members"] == ["jan@example.com"]
