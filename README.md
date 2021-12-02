# supper-bot

## Deploying via AWS Serverless Application Model (SAM)

Edit `supper-bot-example.yml` and change the following:

- `BOT_ID`
- `BOT_TOKEN`
- `BOT_URL`
- `TelegramWebhook` -> `Path` (optional to change)

```
$ sam validate -t supper-bot-example.yml

$ sam build -t supper-bot-example.yml

$ sam deploy -t supper-bot-example.yml
```

The following resources will be created:

- 1 Lambda function (telegram bot webhook handler)
- 1 DyanmoDB table (data storage)
- 1 API Gateway (endpoint for webhook)