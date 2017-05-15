FROM hforge/itools:0.77

# Install ikaaro dependencies
RUN mkdir -p /tmp/ikaaro
ADD ./ /tmp/ikaaro/
RUN pip install -r /tmp/ikaaro/requirements.txt

# Install ikaaro
WORKDIR /tmp/ikaaro
RUN python setup.py install

# Workdir is /home/ikaaro
WORKDIR /home/ikaaro
