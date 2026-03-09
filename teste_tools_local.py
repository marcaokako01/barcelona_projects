from app.services.llm.tools import (
    get_table_pricing,
    get_table_pricing_vapi,
    api_request_tool,
)

def main():
    print("=" * 80)
    print("TESTE 1 - get_table_pricing")
    print("=" * 80)
    try:
        r1 = get_table_pricing.func(
            produto="carro",
            valor_credito_desejado=180000
        )
        print(r1)
    except Exception as e:
        print("ERRO get_table_pricing:", repr(e))

    print("\n" + "=" * 80)
    print("TESTE 2 - get_table_pricing_vapi")
    print("=" * 80)
    try:
        r2 = get_table_pricing_vapi.func(
            produto="carro",
            valor_credito_desejado=180000
        )
        print(r2)
    except Exception as e:
        print("ERRO get_table_pricing_vapi:", repr(e))

    print("\n" + "=" * 80)
    print("TESTE 3 - api_request_tool")
    print("=" * 80)
    try:
        r3 = api_request_tool.func(
            nome="Andre",
            data_hora_iso="2026-03-09 14:00"
        )
        print(r3)
    except Exception as e:
        print("ERRO api_request_tool:", repr(e))


if __name__ == "__main__":
    main()