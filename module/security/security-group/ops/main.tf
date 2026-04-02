resource "aws_security_group" "this" {
  name        = var.name
  description = var.description
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "cidr" {
  for_each = {
    for idx, rule in var.ingress_with_cidr_blocks :
    idx => rule
  }

  security_group_id = aws_security_group.this.id
  from_port         = each.value.from_port
  to_port           = each.value.to_port
  ip_protocol       = each.value.protocol
  cidr_ipv4         = each.value.cidr_blocks
  description       = each.value.description
}

resource "aws_vpc_security_group_ingress_rule" "sg" {
  for_each = {
    for idx, rule in var.ingress_with_source_security_group_id :
    idx => rule
  }

  security_group_id            = aws_security_group.this.id
  from_port                    = each.value.from_port
  to_port                      = each.value.to_port
  ip_protocol                  = each.value.protocol
  referenced_security_group_id = each.value.source_security_group_id
  description                  = each.value.description
}

resource "aws_vpc_security_group_egress_rule" "cidr" {
  for_each = {
    for idx, rule in var.egress_with_cidr_blocks :
    idx => rule
  }

  security_group_id = aws_security_group.this.id
  from_port         = each.value.from_port
  to_port           = each.value.to_port
  ip_protocol       = each.value.protocol
  cidr_ipv4         = each.value.cidr_blocks
  description       = each.value.description
}
