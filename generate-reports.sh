function generate-report() {
    local account="$1"
    local env="$2"

    echo "--------------------------------------------------------------------------------"
    echo "-- Generating report for ${account} ${env}"
    echo "--------------------------------------------------------------------------------"
    echo

    aws-login "${account}" "${env}"
    echo

    make run
    mv "cost-explorer-report.xlsx" "reports/${account}-${env}-cost-explorer-report.xlsx"
}

mkdir -p reports

generate-report agdatascience non-prod
generate-report bos           utility
generate-report bos           dev
generate-report bos           staging
generate-report bos           prod
generate-report cef           embase
generate-report cef           prod
generate-report dkp           non-prod
generate-report dkp           prod
generate-report sc-content    non-prod
generate-report sc-content    prod
generate-report sd-content    non-prod
generate-report sd-content    prod

generate-report databricks    prod
generate-report databricks    nonprod
generate-report dp            nonprod
generate-report dp            prod
generate-report dp            sandbox-nonprod
generate-report dp            tooling

#generate-report recs          dev
#generate-report recs          prod
## generate-report scopus-search non-prod
## generate-report scopus-search prod

## generate-report cef           backup
## generate-report cef           candi

open reports
