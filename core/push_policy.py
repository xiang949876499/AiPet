class PushPolicy:
    medical_terms = ("诊断", "用药", "治疗", "处方", "皮肤病", "抽搐", "大出血")

    def can_send_internal_staff(self, scene: str) -> bool:
        return bool(scene)

    def can_send_to_customer(self, customer, scene: str) -> bool:
        if getattr(customer, "do_not_disturb", False):
            return False
        if getattr(customer, "push_consent_status", "unknown") != "granted":
            return False
        return bool(scene)

    def validate_customer_content(self, content: str, customer) -> str | None:
        if any(term in content for term in self.medical_terms):
            return "medical_content_blocked"
        if not self.can_send_to_customer(customer, scene="customer_message"):
            return "customer_push_blocked"
        return None
