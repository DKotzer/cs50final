import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash


from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses are't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    stocks = db.execute("SELECT symbol, shares, name, price, total FROM portfolio WHERE id = :id", id=session["user_id"])
    totalmoney = 0

    for stock in stocks:
        stockupdate = lookup(stock["symbol"])
        price = stockupdate['price']

        shares = stock["shares"]
        value = shares * price
        totalmoney += value

        db.execute("UPDATE portfolio SET price = :price, total = :value WHERE symbol = :symbol", price=price, value=value, symbol=stock["symbol"])

    cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
    totalmoney += float(cash[0]['cash'])

    return render_template("index.html", stocks=stocks, total=totalmoney, cash=cash[0]['cash'])


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        rows = lookup(request.form.get("symbol"))
        if not rows:
            return apology("must provide valid symbol")
        money = db.execute("SELECT cash FROM users WHERE id = :id;", id=session["user_id"])
        money = money[0]['cash']
        try:
            shares = int(request.form.get("shares"))
            if shares < 1:
                return apology("Must pick 1 or more shares")
        except:
            return apology("Must pick an integer")

        price = rows['price']

        if price * shares > money:
            return apology("not enough funds for transaction, try with less shares")

        db.execute("INSERT INTO trades(symbol, shares, id, price) VALUES(:symbol, :shares, :id, :price)", symbol=rows['symbol'], shares=shares, id=session["user_id"], price=price)

        money -= (price * shares)
        db.execute("UPDATE users SET cash = :money WHERE id = :id", money=money, id=session["user_id"])

        sharecheck = db.execute("SELECT shares, total FROM portfolio WHERE id = :id AND symbol = :symbol", id=session["user_id"], symbol=rows["symbol"])
        totalprice = price * shares

        if sharecheck:
            value = price * (sharecheck[0]['shares'] + shares)
            db.execute("UPDATE portfolio SET total = :total, shares = shares + :shares WHERE id = :id AND symbol = :symbol", shares=shares, total=value, id=session["user_id"], symbol=rows['symbol'])
        else:
            db.execute("INSERT INTO portfolio(id, symbol, shares, name, price, total) VALUES(:id, :symbol, :shares, :name, :price, :total)", id=session["user_id"], symbol=rows['symbol'], shares=shares, name=rows['name'], price=price, total=totalprice)

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/bought", methods=["GET", "POST"])
@login_required
def bought():
    return render_template("bought.html")

@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == "POST":
        deposit = float(request.form.get("deposit"))
        if not deposit:
            return apology("must provide valid ammount")
        money = db.execute("SELECT cash FROM users WHERE id = :id;", id=session["user_id"])
        money = money[0]['cash']
        newTotal = money + deposit
        db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash = newTotal, id=session["user_id"])
        return redirect("/")
    else:
        return render_template("deposit.html")


@app.route("/sold", methods=["GET", "POST"])
@login_required
def sold():
    return render_template("sold.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    stocks = db.execute("SELECT timestamp, symbol, shares, price FROM trades WHERE id = :id", id=session["user_id"])

    for stock in stocks:
        shares = stock["shares"]
        price = stock["price"]

    return render_template("history.html", stocks=stocks)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        rows = lookup(request.form.get("symbol"))
        if not rows:
            return apology("must provide valid symbol")

        price = usd(rows['price'])
        return render_template("result.html", stock=rows, price=price)
    else:
        return render_template("quote.html")


@app.route("/result", methods=["GET", "POST"])
@login_required
def result():
    """Print out results of quote"""

    return render_template("result.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords do not match, try again")

        result = db.execute("INSERT INTO users(username, hash) VALUES(:username, :hash)", username=request.form.get("username"), hash=generate_password_hash(request.form.get("password")))
        if not result:
            return apology("Your chosen username is already in use, try another")

        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        session["user_id"] = rows[0]["id"]
        return redirect("/")

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        symbol = lookup(request.form.get("symbol"))
        if not symbol:
            return apology("must provide a valid symbol")
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session['user_id'])
        cashtotal = cash[0]['cash']
        stock = db.execute("SELECT symbol, shares, total FROM portfolio WHERE id = :id AND symbol = :symbol", id=session['user_id'], symbol=symbol['symbol'])

        try:
            shares = int(request.form.get("shares"))
            if shares < 1:
                return apology("Must pick 1 or more shares")
        except:
            return apology("Must pick an integer")

        if shares > stock[0]["shares"]:
            return apology("you do not have enough shares to sell")
        price = symbol['price']
        sharesx = stock[0]['shares']
        sharesupdate = sharesx - shares
        value = float(price) * (stock[0]['shares'] - shares)

        priceupdate = price * shares + cashtotal
        db.execute("INSERT INTO trades(symbol, shares, id, price) VALUES(:symbol, :shares, :id, :price)", symbol=symbol['symbol'], shares=shares * -1, id=session["user_id"], price=price)

        db.execute("UPDATE portfolio SET shares = :sharesupdate, total = :value WHERE id = :id AND symbol = :symbol", sharesupdate=sharesupdate, value=value, id=session["user_id"], symbol=symbol['symbol'])
        db.execute("UPDATE users SET cash = :priceupdate WHERE id = :id", priceupdate=priceupdate, id=session["user_id"])

        return redirect("/")
    else:
        stocks = db.execute("SELECT symbol FROM portfolio WHERE id = :id", id=session["user_id"])
        return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
