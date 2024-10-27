variable "kube_config" {
  type = string
  default = "~/.kube/config"
}

variable "namespace" {
  type = string
  default = "redditpipeline"
}

variable "docker_username" {
  type = string
  default = "nafisghasemzadeh"
}


# Define environment variables to capture local OS environment variables
variable "REDDIT_CLIENT_ID" {
  description = "Environment variable to be passed to Kubernetes container"
  type        = string
  default     = ""  # Optional: default value if needed
}
variable "REDDIT_CLIENT_SECRET" {
  description = "Environment variable to be passed to Kubernetes container"
  type        = string
  default     = ""  # Optional: default value if needed
}
variable "REDDIT_USER_AGENT" {
  description = "Environment variable to be passed to Kubernetes container"
  type        = string
  default     = ""  # Optional: default value if needed
}
variable "REDDIT_REFRESH_TOKEN" {
  description = "Environment variable to be passed to Kubernetes container"
  type        = string
  default     = ""  # Optional: default value if needed
}

