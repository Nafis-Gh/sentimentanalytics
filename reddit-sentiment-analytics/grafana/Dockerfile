FROM grafana/grafana:latest

# Install required plugins for Cassandra and custom data sources
RUN grafana-cli plugins install hadesarchitect-cassandra-datasource
RUN grafana-cli plugins install yesoreyeram-infinity-datasource

# Install Worldmap and Treemap Panel plugins
RUN grafana-cli plugins install grafana-worldmap-panel
RUN grafana-cli plugins install marcusolsson-treemap-panel

# Copy custom configuration files
COPY config/grafana.ini /etc/grafana/grafana.ini
COPY config/cassandra.yaml /etc/grafana/provisioning/datasources/cassandra.yaml
COPY config/dashboard.yaml /etc/grafana/provisioning/dashboards/dashboard.yaml
COPY config/dashboards /var/lib/grafana/dashboards
