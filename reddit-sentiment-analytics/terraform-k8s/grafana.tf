resource "kubernetes_deployment" "grafana" {
  metadata {
    name      = "grafana"
    namespace = "${var.namespace}"
    labels = {
      "k8s.service" = "grafana"
    }
  }

  depends_on = [
    kubernetes_deployment.cassandra
  ]

  spec {
    replicas = 1

    selector {
      match_labels = {
        "k8s.service" = "grafana"
      }
    }

    template {
      metadata {
        labels = {
          "k8s.network/pipeline-network" = "true"
          "k8s.service" = "grafana"
        }
      }

      spec {
        container {
          name  = "grafana"
          image = "docker.io/${var.docker_username}/grafana:latest"

          port {
            container_port = 3000
          }

          # Environment variables for Grafana settings
          env {
            name  = "GF_AUTH_ANONYMOUS_ENABLED"
            value = "true"
          }
          env {
            name  = "GF_AUTH_ANONYMOUS_ORG_ROLE"
            value = "Viewer"
          }
          env {
            name  = "GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH"
            value = "/var/lib/grafana/dashboards/dashboard.json"
          }
          env {
            name  = "GF_AUTH_DISABLE_SESSION_COOKIE"
            value = "true"
          }
          # Add unsigned plugin allowance here
          env {
            name  = "GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS"
            value = "grafana-worldmap-panel,marcusolsson-treemap-panel"
          }

          image_pull_policy = "Always"
        }

        restart_policy = "Always"
      }
    }
  }
}

# NodePort service for exposing Grafana dashboard
resource "kubernetes_service" "grafana" {
  metadata {
    name      = "grafana"
    namespace = "${var.namespace}"
    labels = {
      "k8s.service" = "grafana"
    }
  }

  depends_on = [kubernetes_deployment.grafana]

  spec {
    port {
      name        = "3000"
      port        = 3000
      target_port = 3000
      node_port   = 30001
      protocol    = "TCP"
    }
    session_affinity = "ClientIP"
    type             = "NodePort"

    selector = {
      "k8s.service" = "grafana"
    }
  }
}
