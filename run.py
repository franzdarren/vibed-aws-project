from app import create_app

app = create_app()

if __name__ == "__main__":
    # host="0.0.0.0" so it's reachable when this later runs on an EC2 instance
    app.run(debug=True, host="0.0.0.0", port=5000)
