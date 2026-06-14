from config import PROMPT_CLASSIFICATION

async def get_classification_prompt(categories: list, user_query: str) -> str:
    """
    Формирует промт для классификации запроса на основе шаблона из конфигурации.

    Args:
        categories: Список доступных категорий
        user_query: Запрос пользователя

    Returns:
        str: Сформированный промт для классификации
    """
    return PROMPT_CLASSIFICATION.format(
        categories=", ".join(categories),
        user_query=user_query
    )
