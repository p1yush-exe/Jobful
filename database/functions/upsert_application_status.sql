create or replace function upsert_application_status(
  p_application_id uuid,
  p_new_status text
)
returns void
language plpgsql
as $$
declare
  v_previous_status text;
begin
  select status
  into v_previous_status
  from applications
  where application_id = p_application_id
  for update;

  if not found then
    raise exception 'application % not found', p_application_id;
  end if;

  update applications
  set status = p_new_status,
      updated_at = now()
  where application_id = p_application_id;

  if v_previous_status is distinct from p_new_status then
    insert into application_status_history (
      application_id,
      previous_status,
      new_status,
      changed_by,
      note
    ) values (
      p_application_id,
      v_previous_status,
      p_new_status,
      null,
      null
    );
  end if;
end;
$$;
