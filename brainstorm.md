# Lets brainstorm on how to make a risk monitoring dashboard

Stack : 
- NextJs (Typescript)
- Yfinance API 
- Postgresql (Or Timescaledb ? i think it's better)
- FastAPI (Python)  -> Industry standard

Architecture : 
Microservice - Event driven ? Kafka as a message broker ?

We're doing a Web dashboard tracking rolling volatility, downside risk, and drawdown for a defined basket. Add alerting logic and data quality guards.

Basket :  S&p 500, Société générale, Siemens 

We want : Risk Metrics Focus
Live Monitoring Output
Decision Support Use

