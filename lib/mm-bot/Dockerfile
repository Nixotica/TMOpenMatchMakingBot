# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Expose port 80
EXPOSE 80

# Expose port 27990 for plugin server
EXPOSE 27990

# Set the working directory in the container
WORKDIR /app

# Copy the requirements.txt file
COPY requirements.txt .

# Install git and any other dependencies
RUN apt-get update && apt-get install -y git curl

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Set the PYTHONPATH environment variable
ENV PYTHONPATH=/app/src

# Copy the source code
COPY src/ /app/src/

# Set the default command to run when the container starts
CMD ["python", "src/main.py"]
