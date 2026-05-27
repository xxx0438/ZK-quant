# 4. Issue PerformanceCert via the real signer
    from app.services.cert_signer import issue_cert, merkle_root_of_snapshots

    snapshot_hashes = result.get("snapshot_hashes", [])  # from enclave
    cert_dict = issue_cert(
        model_id=submission.proposed_model_id,
        model_version="v1.0.0",
        category=submission.category,
        asset=submission.proposed_model_id.split("-")[-1].upper(),
        artifact_sha256=submission.artifact_sha256,
        artifact_size_bytes=result.get("artifact_size_bytes", 0),
        onnx_opset=result.get("onnx_opset", 13),
        kit_sha256=submission.backtest_kit_sha256,
        kit_url=submission.backtest_kit_url,
        dataset_name=result.get("dataset_name", "unknown"),
        dataset_hash=result.get("metrics", {}).get("dataset_hash", ""),
        period_start_ts=result.get("period_start_ts", 0),
        period_end_ts=result.get("period_end_ts", 0),
        snapshot_hashes_root=merkle_root_of_snapshots(snapshot_hashes),
        backtest_metrics=metrics,
        live_metrics=None,
        expires_at=int(time.time()) + settings.cert_default_validity_days * 86400,
    )

    cert = PerformanceCert(
        id=cert_dict["cert_id"],
        model_id=submission.proposed_model_id,
        model_version="v1.0.0",
        backtest_metrics=metrics,
        forward_metrics=None,
        capital_metrics=None,
        attestation=cert_dict,             # full signed cert JSON
        signature=cert_dict["signature"]["value"],
        dataset_hash=cert_dict["dataset"]["hash"],
        harness_hash=submission.backtest_kit_sha256,
        reproducibility_kit_url=submission.backtest_kit_url,
    )
