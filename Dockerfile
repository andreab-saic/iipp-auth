FROM python:3.11-slim

# Set the working directory
WORKDIR /app


# install prerequisites arcgis-api
RUN apt-get update && apt-get dist-upgrade -y
# && apt-get install libkrb5-dev build-essential -y
# arcgis need the above

# Update pip
RUN pip install --upgrade pip

# Copy the requirements file and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application and related files
COPY . /app

# Run Tests during build process and fail build if they fail
# ENV PYTHONPATH=/app/routes
# RUN python -m unittest discover -s tests


# Expose the application port
EXPOSE 80

# Command to run the app with Gunicorn
CMD ["gunicorn", "-w", "4", "--timeout", "120", "--worker-class", "gevent", "app:create_app()", "-b", "0.0.0.0:80"]
