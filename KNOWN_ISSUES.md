# RealTek vs MediaTek Driver Performance

MediaTek adapters seem to perform better.

# iwlwifi requires a scan

iwlwifi uses something called Location Aware Regulatory (LAR) which ignores `iw reg set XX`.

To enable channels and also remove `No IR` to enable injection, we have to do a scan before creating a mon vif. 

# rtl88xxau does not support vif

See title.
