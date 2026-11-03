# whatstocks

A morning dashboard for your own portfolio. You write down what you think
will happen in the world. The dashboard shows how your money lines up with
that, reads the day's news against it, and scores your calls over time.

Your own AI assistant (Claude Code) runs it on your own machine. There is
no server and no account, and your files never leave your computer except
as percentages (see below).

> **Status: spec draft.** Nothing runs yet. Read [docs/SPEC.md](docs/SPEC.md)
> for the design, and [demo/](demo/) for what your files will look like.

## What you see each morning

| Panel | Question it answers |
|---|---|
| **Views** | What do I think will happen, how sure am I, and what did today's news say for or against it? |
| **Exposure** | Where is my money actually exposed (AI build-out, defence, oil, India, ...), and how does that compare with a plain world index fund? |
| **Record** | Were my past calls right? Did my trades follow my own views? |

Above the panels sits the **morning brief**. It covers the day's world events,
and it reads each one through the same four questions:

1. What happened? (with a source link)
2. Where does money move: who pays, and who gets paid?
3. Which themes, regions and holdings of yours does it touch?
4. Does it count for or against any of your views?

The brief does not tell you what to think about an event. It gives you a
fixed way to read one.

## What it will never do

- Tell you to buy or sell anything, or give price targets.
- Place orders, or ask for a broker login that can trade.
- Send money amounts to the AI. The AI sees only tickers and percentages.
- State a fact without a link to a source that the code fetched itself.
- Change your views for you. It shows evidence, and you decide.

## How it will work (planned)

You need [uv](https://docs.astral.sh/uv/) and
[Claude Code](https://claude.com/claude-code). uv installs the right Python
version for you.

```text
git clone https://github.com/Aarrushh/whatstocks
cd whatstocks
uv sync
claude
> /setup      # import a broker CSV, write your first 2-3 views
> /morning    # every morning: refresh, read the news, build the page
```

`/setup` creates a `my/` folder. Git ignores it, so your own data never ends
up in a commit.

## Not financial advice

whatstocks describes your own portfolio and your own stated views. It is a
tool for thinking and keeping a record, not an adviser, and it makes no
recommendations. Any decision you make with it is your own.

## License

MIT. See [LICENSE](LICENSE).
