param(
    [string]$ConfigFile = ".deploy.env",

    [string]$DiscordUserId,

    [string]$ProjectId,

    [string]$DiscordBotToken,

    [string]$Topics = "Etherium/USD news and graph analysis, Bitcoin/USD news and graph analysis, Generic Thai economic news",
    [string]$Region = "us-central1",
    [string]$SchedulerRegion = "us-central1",
    [string]$ServiceName = "daily-news-agent",
    [string]$JobName = "daily-news-agent-daily",
    [string]$Schedule = "0 6 * * *",
    [string]$TimeZone = "Asia/Bangkok",
    [string]$VertexLocation = "global",
    [string]$GeminiModel = "gemini-2.5-flash",
    [int]$NewsItemsPerTopic = 5,
    [string]$DiscordTokenSecretName = "discord-bot-token",
    [switch]$SkipSecretPrompt,
    [switch]$NoPauseOnError
)

$ErrorActionPreference = "Stop"

trap {
    Write-Host ""
    Write-Host "Deployment failed." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Full error:"
    Write-Host ($_ | Out-String)
    if (-not $NoPauseOnError) {
        Read-Host "Press Enter to close this window" | Out-Null
    }
    exit 1
}

function Run-Gcloud {
    param([string[]]$Arguments)
    Write-Host "> gcloud $($Arguments -join ' ')"
    & gcloud @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud command failed: $($Arguments -join ' ')"
    }
}

function Write-Utf8NoBom {
    param(
        [string]$Path,
        [string]$Content
    )

    $Encoding = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($Path, $Content, $Encoding)
}

function Quote-YamlString {
    param([string]$Value)
    return '"' + $Value.Replace('\', '\\').Replace('"', '\"') + '"'
}

function Unquote-ConfigValue {
    param([string]$Value)

    $Trimmed = $Value.Trim()
    if (
        ($Trimmed.StartsWith('"') -and $Trimmed.EndsWith('"')) -or
        ($Trimmed.StartsWith("'") -and $Trimmed.EndsWith("'"))
    ) {
        return $Trimmed.Substring(1, $Trimmed.Length - 2)
    }
    return $Trimmed
}

function Read-DeployConfig {
    param([string]$Path)

    $Config = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $Config
    }

    foreach ($Line in Get-Content -LiteralPath $Path) {
        $Trimmed = $Line.Trim()
        if (-not $Trimmed -or $Trimmed.StartsWith("#")) {
            continue
        }

        $Separator = $Trimmed.IndexOf("=")
        if ($Separator -lt 1) {
            continue
        }

        $Key = $Trimmed.Substring(0, $Separator).Trim()
        $Value = $Trimmed.Substring($Separator + 1)
        $Config[$Key] = Unquote-ConfigValue $Value
    }

    return $Config
}

function Use-ConfigValue {
    param(
        [hashtable]$Config,
        [hashtable]$BoundParameters,
        [string]$ParameterName,
        [string]$Name,
        [string]$CurrentValue
    )

    if ($BoundParameters.ContainsKey($ParameterName)) {
        return $CurrentValue
    }
    if ($Config.ContainsKey($Name)) {
        return $Config[$Name]
    }
    return $CurrentValue
}

function Require-Value {
    param(
        [string]$Name,
        [string]$Value
    )

    if (-not $Value) {
        throw "$Name is required. Put it in $ConfigFile or pass it as a script parameter."
    }
}

function Join-CommandOutput {
    param([object[]]$Output)
    if (-not $Output) {
        return ""
    }
    return ($Output -join "`n").Trim()
}

function Ensure-ServiceAccount {
    param(
        [string]$Name,
        [string]$DisplayName
    )

    $Email = "$Name@$ProjectId.iam.gserviceaccount.com"
    $ExistingEmail = Join-CommandOutput -Output @(& gcloud iam service-accounts list `
        --project $ProjectId `
        --filter "email=$Email" `
        --format "value(email)")

    if (-not $ExistingEmail) {
        Run-Gcloud @("iam", "service-accounts", "create", $Name, "--display-name", $DisplayName, "--project", $ProjectId)
    }
    return $Email
}

function Test-SecretExists {
    param([string]$Name)

    $ExistingSecret = Join-CommandOutput -Output @(& gcloud secrets list `
        --project $ProjectId `
        --filter "name:$Name" `
        --format "value(name)")
    return [bool]$ExistingSecret
}

function Test-SchedulerJobExists {
    param([string]$Name)

    $ExistingJob = Join-CommandOutput -Output @(& gcloud scheduler jobs list `
        --location $SchedulerRegion `
        --project $ProjectId `
        --filter "name:$Name" `
        --format "value(name)")
    return [bool]$ExistingJob
}

if (-not [System.IO.Path]::IsPathRooted($ConfigFile)) {
    $RootConfigFile = Join-Path (Split-Path $PSScriptRoot -Parent) $ConfigFile
    if (Test-Path -LiteralPath $RootConfigFile) {
        $ConfigFile = $RootConfigFile
    }
}

$DeployConfig = Read-DeployConfig -Path $ConfigFile
$ProjectId = Use-ConfigValue -Config $DeployConfig -BoundParameters $PSBoundParameters -ParameterName "ProjectId" -Name "PROJECT_ID" -CurrentValue $ProjectId
$DiscordUserId = Use-ConfigValue -Config $DeployConfig -BoundParameters $PSBoundParameters -ParameterName "DiscordUserId" -Name "DISCORD_USER_ID" -CurrentValue $DiscordUserId
$DiscordBotToken = Use-ConfigValue -Config $DeployConfig -BoundParameters $PSBoundParameters -ParameterName "DiscordBotToken" -Name "DISCORD_BOT_TOKEN" -CurrentValue $DiscordBotToken
$Topics = Use-ConfigValue -Config $DeployConfig -BoundParameters $PSBoundParameters -ParameterName "Topics" -Name "TOPICS" -CurrentValue $Topics
$Region = Use-ConfigValue -Config $DeployConfig -BoundParameters $PSBoundParameters -ParameterName "Region" -Name "REGION" -CurrentValue $Region
$SchedulerRegion = Use-ConfigValue -Config $DeployConfig -BoundParameters $PSBoundParameters -ParameterName "SchedulerRegion" -Name "SCHEDULER_REGION" -CurrentValue $SchedulerRegion
$ServiceName = Use-ConfigValue -Config $DeployConfig -BoundParameters $PSBoundParameters -ParameterName "ServiceName" -Name "SERVICE_NAME" -CurrentValue $ServiceName
$JobName = Use-ConfigValue -Config $DeployConfig -BoundParameters $PSBoundParameters -ParameterName "JobName" -Name "JOB_NAME" -CurrentValue $JobName
$Schedule = Use-ConfigValue -Config $DeployConfig -BoundParameters $PSBoundParameters -ParameterName "Schedule" -Name "SCHEDULE" -CurrentValue $Schedule
$TimeZone = Use-ConfigValue -Config $DeployConfig -BoundParameters $PSBoundParameters -ParameterName "TimeZone" -Name "TIME_ZONE" -CurrentValue $TimeZone
$VertexLocation = Use-ConfigValue -Config $DeployConfig -BoundParameters $PSBoundParameters -ParameterName "VertexLocation" -Name "VERTEX_LOCATION" -CurrentValue $VertexLocation
$GeminiModel = Use-ConfigValue -Config $DeployConfig -BoundParameters $PSBoundParameters -ParameterName "GeminiModel" -Name "GEMINI_MODEL" -CurrentValue $GeminiModel
$DiscordTokenSecretName = Use-ConfigValue -Config $DeployConfig -BoundParameters $PSBoundParameters -ParameterName "DiscordTokenSecretName" -Name "DISCORD_TOKEN_SECRET_NAME" -CurrentValue $DiscordTokenSecretName

if ((-not $PSBoundParameters.ContainsKey("NewsItemsPerTopic")) -and $DeployConfig.ContainsKey("NEWS_ITEMS_PER_TOPIC")) {
    $NewsItemsPerTopic = [int]$DeployConfig["NEWS_ITEMS_PER_TOPIC"]
}

Require-Value -Name "PROJECT_ID" -Value $ProjectId
Require-Value -Name "DISCORD_USER_ID" -Value $DiscordUserId

Run-Gcloud @("config", "set", "project", $ProjectId)
Run-Gcloud @(
    "services", "enable",
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudscheduler.googleapis.com",
    "secretmanager.googleapis.com",
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "--project", $ProjectId
)

$RunServiceAccount = Ensure-ServiceAccount -Name "${ServiceName}-run" -DisplayName "$ServiceName runtime"
$SchedulerServiceAccount = Ensure-ServiceAccount -Name "${ServiceName}-scheduler" -DisplayName "$ServiceName scheduler"
$ProjectNumber = Join-CommandOutput -Output @(& gcloud projects describe $ProjectId --format "value(projectNumber)" --project $ProjectId)
$BuildServiceAccount = "${ProjectNumber}-compute@developer.gserviceaccount.com"

if (-not $SkipSecretPrompt) {
    if (-not $DiscordBotToken) {
        $SecureToken = Read-Host "Paste your Discord bot token" -AsSecureString
        $Bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureToken)
        try {
            $DiscordBotToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Bstr)
        }
        finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Bstr)
        }
    }

    $SecretFile = New-TemporaryFile
    try {
        Write-Utf8NoBom -Path $SecretFile.FullName -Content $DiscordBotToken
        if (-not (Test-SecretExists -Name $DiscordTokenSecretName)) {
            Run-Gcloud @("secrets", "create", $DiscordTokenSecretName, "--data-file=$($SecretFile.FullName)", "--project", $ProjectId)
        }
        else {
            Run-Gcloud @("secrets", "versions", "add", $DiscordTokenSecretName, "--data-file=$($SecretFile.FullName)", "--project", $ProjectId)
        }
    }
    finally {
        Remove-Item -LiteralPath $SecretFile.FullName -Force -ErrorAction SilentlyContinue
    }
}

Run-Gcloud @(
    "projects", "add-iam-policy-binding", $ProjectId,
    "--member=serviceAccount:$RunServiceAccount",
    "--role=roles/aiplatform.user",
    "--quiet"
)

Run-Gcloud @(
    "projects", "add-iam-policy-binding", $ProjectId,
    "--member=serviceAccount:$BuildServiceAccount",
    "--role=roles/run.builder",
    "--quiet"
)

Run-Gcloud @(
    "iam", "service-accounts", "add-iam-policy-binding", $RunServiceAccount,
    "--member=serviceAccount:$BuildServiceAccount",
    "--role=roles/iam.serviceAccountUser",
    "--project", $ProjectId,
    "--quiet"
)

Run-Gcloud @(
    "secrets", "add-iam-policy-binding", $DiscordTokenSecretName,
    "--member=serviceAccount:$RunServiceAccount",
    "--role=roles/secretmanager.secretAccessor",
    "--project", $ProjectId,
    "--quiet"
)

$EnvFile = New-TemporaryFile
try {
    $EnvYaml = @"
NEWS_TOPICS: $(Quote-YamlString $Topics)
DISCORD_USER_ID: $(Quote-YamlString $DiscordUserId)
NEWS_ITEMS_PER_TOPIC: $(Quote-YamlString "$NewsItemsPerTopic")
DIGEST_TIMEZONE: $(Quote-YamlString $TimeZone)
GOOGLE_CLOUD_PROJECT: $(Quote-YamlString $ProjectId)
GOOGLE_CLOUD_LOCATION: $(Quote-YamlString $VertexLocation)
GOOGLE_GENAI_USE_VERTEXAI: "True"
GEMINI_MODEL: $(Quote-YamlString $GeminiModel)
"@
    Write-Utf8NoBom -Path $EnvFile.FullName -Content $EnvYaml

    Run-Gcloud @(
        "run", "deploy", $ServiceName,
        "--source", ".",
        "--region", $Region,
        "--service-account", $RunServiceAccount,
        "--no-allow-unauthenticated",
        "--env-vars-file", $EnvFile.FullName,
        "--update-secrets", "DISCORD_BOT_TOKEN=${DiscordTokenSecretName}:latest",
        "--project", $ProjectId
    )
}
finally {
    Remove-Item -LiteralPath $EnvFile.FullName -Force -ErrorAction SilentlyContinue
}

Run-Gcloud @(
    "run", "services", "add-iam-policy-binding", $ServiceName,
    "--region", $Region,
    "--member=serviceAccount:$SchedulerServiceAccount",
    "--role=roles/run.invoker",
    "--project", $ProjectId,
    "--quiet"
)

$ServiceUrl = Join-CommandOutput -Output @(& gcloud run services describe $ServiceName --region $Region --format "value(status.url)" --project $ProjectId)
if (-not $ServiceUrl) {
    throw "Could not resolve Cloud Run service URL."
}

$RunUri = "$ServiceUrl/run"
if (Test-SchedulerJobExists -Name $JobName) {
    Run-Gcloud @(
        "scheduler", "jobs", "update", "http", $JobName,
        "--location", $SchedulerRegion,
        "--schedule", $Schedule,
        "--time-zone", $TimeZone,
        "--uri", $RunUri,
        "--http-method", "POST",
        "--oidc-service-account-email", $SchedulerServiceAccount,
        "--oidc-token-audience", $ServiceUrl,
        "--project", $ProjectId
    )
}
else {
    Run-Gcloud @(
        "scheduler", "jobs", "create", "http", $JobName,
        "--location", $SchedulerRegion,
        "--schedule", $Schedule,
        "--time-zone", $TimeZone,
        "--uri", $RunUri,
        "--http-method", "POST",
        "--oidc-service-account-email", $SchedulerServiceAccount,
        "--oidc-token-audience", $ServiceUrl,
        "--project", $ProjectId
    )
}

Write-Host ""
Write-Host "Deployed $ServiceName."
Write-Host "Cloud Run URL: $ServiceUrl"
Write-Host "Scheduler job: $JobName ($Schedule, $TimeZone)"
Write-Host "To send a test digest now:"
Write-Host "gcloud scheduler jobs run $JobName --location $SchedulerRegion --project $ProjectId"
